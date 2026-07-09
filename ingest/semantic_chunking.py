import logging
from typing import List, Any
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.core import Document

logger = logging.getLogger(__name__)


def create_semantic_splitter(embed_model, buffer_size=1, breakpoint_percentile_threshold=95):
    """
    Create a SemanticSplitterNodeParser for semantic chunking.

    Args:
        embed_model: Embedding model used to compute sentence similarity for
            breakpoint detection
        buffer_size: Number of sentences to include on either side of a split
        breakpoint_percentile_threshold: Percentile threshold for splits (higher
            = fewer, larger chunks)
    """
    return SemanticSplitterNodeParser(
        buffer_size=buffer_size,
        breakpoint_percentile_threshold=breakpoint_percentile_threshold,
        embed_model=embed_model,
    )


def generate_nodes_from_documents(semantic_splitter, documents: List[Document]) -> List[Any]:
    """
    Generate semantically-chunked nodes from documents.

    Same as demo-2-semantic-chunking-rag/semantic_chunking.py:generate_nodes_from_documents().
    """
    nodes = semantic_splitter.get_nodes_from_documents(documents)
    logger.info(f"Generated {len(nodes)} node(s) using semantic chunking")
    return nodes
