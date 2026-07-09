from typing import List, Optional
from pydantic import BaseModel, Field

class DiscoveryRequest(BaseModel):
    query: str = Field(..., description="The search query for literature discovery")
    limit: int = Field(default=10, description="Maximum number of papers to return")
    thread_id: Optional[str] = Field(default=None, description="Optional conversation thread ID")

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
