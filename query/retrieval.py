import logging
from typing import List, Dict, Any

from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator

from ingest.indexing_service import get_or_create_index

logger = logging.getLogger(__name__)


def retrieve_chunks(document_id: str, question: str, similarity_top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Hybrid-style retrieval (semantic similarity + document_id metadata filter).
    """
    index = get_or_create_index()

    filters = MetadataFilters(
        filters=[
            MetadataFilter(key="app_document_id", value=document_id, operator=FilterOperator.EQ)  # <-- CHANGED key
        ]
    )
    retriever = index.as_retriever(similarity_top_k=similarity_top_k, filters=filters)
    nodes = retriever.retrieve(question)

    chunks = []
    for node in nodes:
        chunks.append({
            "chunk_id": node.node.node_id,
            "text": node.node.text,
            "score": float(node.score) if node.score is not None else 0.0,
            "page": node.node.metadata.get("page"),
            "chunk_type": node.node.metadata.get("chunk_type", "text"),
        })

    logger.info(f"Retrieved {len(chunks)} chunk(s) for document_id={document_id}")

    if not chunks:
        logger.warning(
            f"Zero chunks retrieved for document_id={document_id}. "
            f"If this persists, verify app_document_id metadata was actually "
            f"stored on the indexed nodes (check the vector store table directly)."
        )

    return chunks