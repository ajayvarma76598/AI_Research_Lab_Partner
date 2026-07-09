import logging
import os
from typing import List
from llama_parse import LlamaParse

from ingest.table_extraction import find_markdown_tables

import re

logger = logging.getLogger(__name__)


def extract_title_from_text(text: str, default_filename: str) -> str:
    """
    Attempt to extract a readable title from the parsed markdown text.
    Uses the first header or first non-empty line.
    """
    # Try finding the first header
    match = re.search(r'^\s*#+\s+(.+)$', text, re.MULTILINE)
    if match:
        title = match.group(1).strip()
        if 3 < len(title) < 200:
            return title
            
    # Fallback to first non-empty line
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        title = lines[0].lstrip('#*').strip()
        if 3 < len(title) < 200:
            return title
            
    return default_filename


def load_document_text(pdf_path: str) -> str:
    """
    Load and parse PDF document to markdown using LlamaParse.
    """
    llama_parse_api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    if not llama_parse_api_key:
        raise EnvironmentError(
            "Missing LLAMA_CLOUD_API_KEY in environment. Get one from https://cloud.llamaindex.ai/"
        )

    parser_lp = LlamaParse(result_type="markdown", verbose=True)
    documents = parser_lp.load_data(pdf_path)

    if not documents or not documents[0].text:
        raise ValueError("No content returned by LlamaParse.")

    full_text = "\n\n".join(doc.text for doc in documents if getattr(doc, "text", ""))
    logger.info(f"LlamaParse returned {len(documents)} document(s), combined length {len(full_text)} chars")
    return full_text


def extract_tables_from_text(text: str) -> List[str]:
    """
    Extract markdown tables from the parsed text.
    """
    tables = find_markdown_tables(text)
    table_strings = [tb[2] for tb in tables]
    logger.info(f"Extracted {len(table_strings)} table(s) from document")
    return table_strings


def strip_tables_from_text(text: str, tables: List[str]) -> str:
    """
    Remove table blocks from the main text so they aren't double-indexed
    as both a plain-text chunk AND a table node.
    """
    cleaned = text
    for table in tables:
        cleaned = cleaned.replace(table, "")
    return cleaned
