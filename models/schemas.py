from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB, from MAX_FILE_SIZE_MB env
MAX_QUERY_LENGTH = 2000
ALLOWED_EXTENSIONS = {".pdf"}


# ============================================================================
# /ingest/document schemas
# ============================================================================
class UrlIngestRequest(BaseModel):
    url: str = Field(..., description="URL of the PDF document to ingest")


class IngestResponse(BaseModel):
    status: str = Field(..., description="'completed' or 'partial_failure'")
    document_id: str
    file_hash: str
    chunks_indexed: int
    chunks_failed: int
    figures_processed: int
    tables_processed: int
    metadata: Dict[str, Any]
    warnings: List[str] = []
    processing_time_sec: float


class DocumentInfoResponse(BaseModel):
    """Response model for fetching document metadata."""
    document_id: str
    file_hash: str
    title: Optional[str] = None
    source_filename: Optional[str] = None
    chunks_indexed: int
    tables_processed: int
    figures_processed: int
    created_at: str


# ============================================================================
# /query schemas
# ============================================================================
class QueryRequest(BaseModel):
    """Request model for POST /query."""
    document_id: str = Field(..., description="ID of the ingested document to query")
    question: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH)
    thread_id: Optional[str] = Field(
        default=None,
        description="Optional conversation thread ID for multi-turn follow-ups "
                    "(matches LangGraph checkpointer thread_id from demo-3-multi-turn-support-agent)",
    )

    @field_validator("question")
    @classmethod
    def validate_question(cls, v):
        if not v or not v.strip():
            raise ValueError("Question cannot be empty")
        return v.strip()


class Citation(BaseModel):
    chunk_id: str
    page: Optional[int] = None
    snippet_ref: Optional[str] = None


class QueryResponse(BaseModel):
    """Response model for POST /query."""
    query_id: str
    answer: str
    citations: List[Citation] = []
    confidence: float
    faithfulness: float
    relevance: float
    agent_used: str
    needs_clarification: bool
    clarification_prompt: Optional[str] = None
    escalated: bool
    thread_id: str
    processing_time_sec: float
    cached: bool = False


# ============================================================================
# /compare schemas
# ============================================================================
class CompareRequest(BaseModel):
    """Request model for POST /compare."""
    document_ids: List[str] = Field(..., description="List of document IDs to compare", min_length=2, max_length=5)
    question: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH)
    thread_id: Optional[str] = Field(default=None, description="Optional conversation thread ID")

class CompareResponse(BaseModel):
    """Response model for POST /compare."""
    query_id: str
    answer: str
    citations: List[Citation] = []
    thread_id: str
    processing_time_sec: float
    cached: bool = False
