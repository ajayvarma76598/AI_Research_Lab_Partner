from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

class DiscoveryRequest(BaseModel):
    query: str = Field(..., description="The search query for literature discovery")
    limit: int = Field(default=10, description="Maximum number of papers to return")
    thread_id: Optional[str] = Field(default=None, description="Optional conversation thread ID")

    @field_validator("query")
    @classmethod
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        if len(v.strip().split()) < 3:
            raise ValueError("Please frame your question as a complete sentence or phrase (at least 3 words).")
        return v.strip()

class DiscoveredPaper(BaseModel):
    paper_id: str
    title: str
    authors: List[str]
    abstract: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None

class DiscoveryResponse(BaseModel):
    results: List[DiscoveredPaper]
    thread_id: str
    processing_time_sec: float
    cached: bool = False
