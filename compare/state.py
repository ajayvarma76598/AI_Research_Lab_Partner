from typing import TypedDict, List, Dict, Any, Annotated
from langgraph.graph.message import add_messages

class CompareState(TypedDict):
    messages: Annotated[list, add_messages]
    query_id: str
    document_ids: List[str]
    question: str
    retrieved_chunks: List[Dict[str, Any]]
    draft_answer: str
    critique: str
    is_satisfactory: bool
    iteration: int
    citations_count: int
