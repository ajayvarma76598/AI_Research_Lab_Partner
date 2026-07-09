from typing import TypedDict, List, Dict, Any

class CompareState(TypedDict):
    query_id: str
    document_ids: List[str]
    question: str
    retrieved_chunks: List[Dict[str, Any]]
    draft_answer: str
    critique: str
    is_satisfactory: bool
    iteration: int
    citations_count: int
