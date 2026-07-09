import hashlib
import logging
import os
import tempfile
import time
import uuid
import asyncio
from pathlib import Path
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
import requests
import io

from models.schemas import IngestResponse, MAX_FILE_SIZE, ALLOWED_EXTENSIONS, UrlIngestRequest, DocumentInfoResponse
from auth.jwt import get_current_user, User
from db.models import DocumentRecord, get_session
from langfuse.decorators import observe, langfuse_context
from ingest.document_parser import load_document_text, extract_tables_from_text, strip_tables_from_text, extract_title_from_text
from ingest.image_extraction import extract_images_from_pdf
from ingest.captioning import generate_caption
from ingest.indexing_service import index_text_document, index_table_nodes, index_figure_nodes
from config import get_llm

logger = logging.getLogger(__name__)
router = APIRouter()


def _hash_file(content: bytes) -> str:
    """SHA-256 idempotency hash. Not from a demo file - small addition to
    satisfy the idempotency requirement from our design plan."""
    return hashlib.sha256(content).hexdigest()


@router.post("/ingest/document", response_model=IngestResponse)
@observe(as_type="trace")
async def ingest_document(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    langfuse_context.update_current_trace(name="ingest_document", input={"filename": file.filename})
    start_time = time.time()
    warnings = []

    # ---- Validate ----
    if not file.filename or Path(file.filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds maximum allowed size")

    file_hash = _hash_file(content)

    # ---- Idempotency check ----
    session = get_session()
    existing = session.query(DocumentRecord).filter_by(file_hash=file_hash).first()
    if existing:
        session.close()
        logger.info(f"Duplicate upload detected, returning existing document_id={existing.document_id}")
        return IngestResponse(
            status="completed",
            document_id=existing.document_id,
            file_hash=file_hash,
            chunks_indexed=existing.chunks_indexed,
            chunks_failed=existing.chunks_failed,
            figures_processed=existing.figures_processed,
            tables_processed=existing.tables_processed,
            metadata=existing.metadata_json or {},
            warnings=["Document already ingested - returning cached result"],
            processing_time_sec=0.0,
        )

    document_id = f"doc_{uuid.uuid4().hex[:8]}"

    # ---- Save to temp file for parsing ----
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(content)
        tmp_path = tmp_file.name

    chunks_indexed = 0
    chunks_failed = 0
    tables_processed = 0
    figures_processed = 0

    try:
        # ---- 1. Parse text + tables via LlamaParse (demo-3-unified-multimodal) ----
        @observe(as_type="span", name="document_parser")
        def _parse_docs():
            _full_text = load_document_text(tmp_path)
            _tables = extract_tables_from_text(_full_text)
            _text_only = strip_tables_from_text(_full_text, _tables)
            langfuse_context.update_current_observation(output={"text_length": len(_full_text), "tables_found": len(_tables)})
            return _full_text, _tables, _text_only
            
        # ---- 2. Extract + caption images via PyMuPDF + vision (demo-2-processing-image) ----
        @observe(as_type="span", name="image_extraction_and_captioning")
        def _extract_images():
            _figure_captions = []
            with tempfile.TemporaryDirectory() as img_dir:
                try:
                    images = extract_images_from_pdf(tmp_path, img_dir)
                    for img in images:
                        try:
                            caption = generate_caption(img["path"])
                            _figure_captions.append({
                                "caption": caption,
                                "page": img["page"],
                                "path": img["path"],
                            })
                        except Exception as e:
                            logger.warning(f"Caption generation failed for {img['path']}: {e}")
                            warnings.append(f"Figure on page {img['page']} could not be captioned")
                except Exception as e:
                    logger.warning(f"Image extraction failed: {e}")
                    warnings.append("Image extraction encountered an error")
            langfuse_context.update_current_observation(output={"figures_captioned": len(_figure_captions)})
            return _figure_captions
            
        # RUN CONCURRENTLY
        parse_task = asyncio.to_thread(_parse_docs)
        extract_task = asyncio.to_thread(_extract_images)
        (full_text, tables, text_only), figure_captions = await asyncio.gather(parse_task, extract_task)

        # ---- 3. Semantic chunking + index text (demo-2-semantic-chunking-rag) ----
        @observe(as_type="span", name="indexing")
        def _index_all(ci, cf, tp, fp):
            try:
                text_nodes = index_text_document(document_id, text_only, file.filename)
                ci += len(text_nodes)
            except Exception as e:
                logger.error(f"Text indexing failed: {e}")
                cf += 1
                warnings.append("Some text chunks failed to index")

            # ---- 4. Index tables (demo-1-table-extraction) ----
            try:
                table_nodes = index_table_nodes(document_id, file.filename, tables)
                tp = len(table_nodes)
                ci += len(table_nodes)
            except Exception as e:
                logger.error(f"Table indexing failed: {e}")
                warnings.append("Some tables failed to index")

            # ---- 5. Index figure captions ----
            try:
                figure_nodes = index_figure_nodes(document_id, file.filename, figure_captions)
                fp = len(figure_nodes)
                ci += len(figure_nodes)
            except Exception as e:
                logger.error(f"Figure indexing failed: {e}")
                warnings.append("Some figures failed to index")

            langfuse_context.update_current_observation(output={
                "chunks_indexed": ci,
                "tables_processed": tp,
                "figures_processed": fp,
            })
            return ci, cf, tp, fp

        chunks_indexed, chunks_failed, tables_processed, figures_processed = await asyncio.to_thread(
            _index_all, chunks_indexed, chunks_failed, tables_processed, figures_processed
        )

        extracted_title = await asyncio.to_thread(extract_title_from_text, full_text, file.filename)

        metadata = {
            "title": extracted_title,
            "tables_found": len(tables),
            "figures_found": len(figure_captions),
        }

        # ---- Persist document record (idempotency + structured metadata) ----
        record = DocumentRecord(
            document_id=document_id,
            file_hash=file_hash,
            title=extracted_title,
            source_filename=file.filename,
            metadata_json=metadata,
            chunks_indexed=chunks_indexed,
            chunks_failed=chunks_failed,
            tables_processed=tables_processed,
            figures_processed=figures_processed,
        )
        session.add(record)
        session.commit()
        session.close()

        processing_time = round(time.time() - start_time, 2)
        status = "partial_failure" if chunks_failed > 0 or warnings else "completed"

        langfuse_context.update_current_trace(output={
            "document_id": document_id,
            "status": status,
            "processing_time_sec": processing_time,
        })

        return IngestResponse(
            status=status,
            document_id=document_id,
            file_hash=file_hash,
            chunks_indexed=chunks_indexed,
            chunks_failed=chunks_failed,
            figures_processed=figures_processed,
            tables_processed=tables_processed,
            metadata=metadata,
            warnings=warnings,
            processing_time_sec=processing_time,
        )

    except Exception as e:
        session.close()
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/documents", response_model=List[DocumentInfoResponse])
def get_all_documents(user: User = Depends(get_current_user)):
    """Retrieve all successfully ingested documents."""
    session = get_session()
    try:
        docs = session.query(DocumentRecord).order_by(DocumentRecord.created_at.desc()).all()
        return [
            DocumentInfoResponse(
                document_id=d.document_id,
                file_hash=d.file_hash,
                title=d.title,
                source_filename=d.source_filename,
                chunks_indexed=d.chunks_indexed,
                tables_processed=d.tables_processed,
                figures_processed=d.figures_processed,
                created_at=d.created_at.isoformat() if d.created_at else ""
            ) for d in docs
        ]
    except Exception as e:
        logger.error(f"Failed to fetch documents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch documents")
    finally:
        session.close()


@router.post("/ingest/url", response_model=IngestResponse)
async def ingest_url(request: UrlIngestRequest, user: User = Depends(get_current_user)):
    try:
        def _download():
            res = requests.get(request.url, timeout=30)
            res.raise_for_status()
            return res.content
            
        content = await asyncio.to_thread(_download)
    except Exception as e:
        logger.error(f"Failed to download URL: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to download URL: {str(e)}")

    filename = request.url.split("/")[-1]
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    mock_file = UploadFile(filename=filename, file=io.BytesIO(content))
    return await ingest_document(file=mock_file)
