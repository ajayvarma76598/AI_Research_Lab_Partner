from typing import TypedDict, Annotated, List, Optional, Dict, Any
from langgraph.graph.message import add_messages


class QueryState(TypedDict):
    messages: Annotated[list, add_messages]
    document_id: str
    question: str
    agent_used: str
    retrieved_chunks: List[Dict[str, Any]]
    draft_answer: str
    faithfulness: float
    relevance: float
    confidence: float
    iteration: int
    needs_clarification: bool
    clarification_prompt: Optional[str]
    escalated: bool
    slo_met: bool
