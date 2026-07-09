import logging
import re
from typing import List, Tuple, Dict, Any

from llama_index.core.schema import TextNode
from llama_index.llms.azure_openai import AzureOpenAI

logger = logging.getLogger(__name__)


def find_markdown_tables(md_text: str) -> List[Tuple[int, int, str]]:
    """
    Extract markdown table blocks from LlamaParse's markdown output.
    """
    lines = md_text.splitlines()
    tables: List[Tuple[int, int, str]] = []

    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("|") and "|" in lines[i].strip()[1:]:
            header_idx = i
            if i + 1 < len(lines):
                sep = lines[i + 1].strip()
                if sep.startswith("|") and re.fullmatch(r"\|[\-:\s\|]+\|", sep):
                    j = i + 2
                    while j < len(lines) and lines[j].strip().startswith("|"):
                        j += 1
                    table_block = "\n".join(lines[header_idx:j]).strip()
                    start_char = len("\n".join(lines[:header_idx])) + (1 if header_idx > 0 else 0)
                    end_char = start_char + len(table_block)
                    tables.append((start_char, end_char, table_block))
                    i = j
                    continue
        i += 1

    logger.info(f"Extracted {len(tables)} markdown table(s) from document")
    return tables


def summarize_table(llm: AzureOpenAI, table_md: str) -> str:
    """
    Summarize a markdown table into a natural language description.

    Same as demo-1-table-extraction/table-processing.py:summarize_table(),
    including the content-filter fallback.
    """
    prompt = (
        "Summarize the following markdown table in a single sentence. "
        "Include key figures and relationships. Be concise and factual.\n\n"
        f"Table:\n{table_md}\n\n"
        "Summary:"
    )
    try:
        resp = llm.complete(prompt)
        return resp.text.strip()
    except Exception as e:
        error_msg = str(e)
        if "content_filter" in error_msg or "content management policy" in error_msg:
            logger.warning("Content filter triggered. Using fallback summary based on table structure.")
            lines = table_md.strip().split("\n")
            headers = lines[0] if lines else "table"
            return f"Table containing data with columns: {headers[:100]}"
        raise


def build_nodes_from_tables(
    source_name: str,
    table_markdowns: List[str],
    llm: AzureOpenAI,
    additional_metadata: Dict[str, Any] = None,
) -> List[TextNode]:
    """
    Build TextNode objects from table markdowns with LLM-generated summaries.

    Same as demo-1-table-extraction/table-processing.py:build_nodes_from_tables().
    Each node is tagged chunk_type="table" so retrieval can filter by type
    (extends the demo slightly to match our unified metadata scheme).
    """
    nodes: List[TextNode] = []
    for idx, table_md in enumerate(table_markdowns):
        summary = summarize_table(llm, table_md)
        metadata = {
            "source": source_name,
            "chunk_type": "table",
            "table_index": idx,
        }
        if additional_metadata:
            metadata.update(additional_metadata)

        node = TextNode(
            text=f"{summary}\n\n{table_md}",
            metadata=metadata,
        )
        nodes.append(node)

    logger.info(f"Built {len(nodes)} table node(s) with summaries")
    return nodes
