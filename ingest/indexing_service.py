import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from llama_index.core import VectorStoreIndex, StorageContext, Document
from llama_index.core.schema import TextNode

from config import get_vector_store, get_embed_model, get_llm
from ingest.semantic_chunking import create_semantic_splitter, generate_nodes_from_documents
from ingest.table_extraction import build_nodes_from_tables

logger = logging.getLogger(__name__)

_index: Optional[VectorStoreIndex] = None


def get_file_metadata(file_path: str, document_id: str) -> Dict[str, Any]:
    """
    Build metadata dict for a document.
    """
    path = Path(file_path)
    return {
        "source": path.name,
        "app_document_id": document_id,   # <-- CHANGED from "document_id"
        "file_extension": path.suffix.lower(),
        "file_size": path.stat().st_size if path.exists() else 0,
    }


def get_or_create_index() -> VectorStoreIndex:
    """
    Load existing index from PostgreSQL/pgvector, or create a new empty one.
    """
    global _index
    if _index is not None:
        return _index

    vector_store = get_vector_store()
    embed_model = get_embed_model()
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    try:
        _index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            embed_model=embed_model,
        )
        logger.info("Loaded existing index from PostgreSQL")
    except Exception as e:
        logger.info(f"Could not load existing index ({e}), creating new empty index")
        _index = VectorStoreIndex(nodes=[], storage_context=storage_context, embed_model=embed_model)

    return _index


def index_text_document(
    document_id: str, text: str, source_name: str, use_semantic_splitter: bool = True
) -> List[TextNode]:
    """
    Chunk (semantic splitter) and index the main document text.
    """
    index = get_or_create_index()
    embed_model = get_embed_model()

    doc = Document(
        text=text,
        metadata=get_file_metadata(source_name, document_id),
    )

    if use_semantic_splitter:
        splitter = create_semantic_splitter(embed_model)
        nodes = generate_nodes_from_documents(splitter, [doc])
    else:
        # Fallback default chunking, same as demo-1-basic-llamaindex-pipeline
        nodes = [doc]

    for node in nodes:
        node.metadata["chunk_type"] = "text"
        node.metadata["app_document_id"] = document_id   # <-- CHANGED from "document_id"
        index.insert_nodes([node]) if hasattr(index, "insert_nodes") else index.insert(node)

    logger.info(f"Indexed {len(nodes)} text node(s) for document {document_id}")
    return nodes


def index_table_nodes(document_id: str, source_name: str, table_markdowns: List[str]) -> List[TextNode]:
    """
    Summarize and index extracted tables.
    """
    if not table_markdowns:
        return []

    index = get_or_create_index()
    llm = get_llm()
    nodes = build_nodes_from_tables(
        source_name=source_name,
        table_markdowns=table_markdowns,
        llm=llm,
        additional_metadata={"app_document_id": document_id},   # <-- CHANGED key
    )
    index.insert_nodes(nodes)
    logger.info(f"Indexed {len(nodes)} table node(s) for document {document_id}")
    return nodes


def index_figure_nodes(document_id: str, source_name: str, figure_captions: List[Dict[str, Any]]) -> List[TextNode]:
    """
    Index figure/image captions as their own nodes (chunk_type="figure").
    """
    if not figure_captions:
        return []

    index = get_or_create_index()
    nodes = []
    for fig in figure_captions:
        node = TextNode(
            text=fig["caption"],
            metadata={
                "source": source_name,
                "app_document_id": document_id,   # <-- CHANGED from "document_id"
                "chunk_type": "figure",
                "page": fig.get("page"),
                "image_path": fig.get("path"),
            },
        )
        nodes.append(node)

    index.insert_nodes(nodes)
    logger.info(f"Indexed {len(nodes)} figure node(s) for document {document_id}")
    return nodes