import logging
import os
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from query.state import QueryState
from query.manager_node import manager_node
from query.specialist_node import specialist_node
from query.reflection_node import reflection_node
from query.handoff import send_handoff_email

logger = logging.getLogger(__name__)

MAX_REFLECTION_ITERATIONS = int(os.getenv("MAX_REFLECTION_ITERATIONS", 3))


def should_continue(state: QueryState) -> str:
    """
    Conditional router after reflection.
    """
    if state.get("slo_met"):
        logger.info("ROUTER: SLO met, routing to complete")
        return "complete"

    if state.get("iteration", 0) >= MAX_REFLECTION_ITERATIONS:
        logger.warning(f"ROUTER: Max iterations ({MAX_REFLECTION_ITERATIONS}) reached, escalating")
        return "escalate"

    logger.info(f"ROUTER: SLO not met, retrying (iteration {state.get('iteration', 0)})")
    return "retry"


def escalate_node(state: QueryState) -> dict:
    """Terminal node: send handoff email and mark state as escalated."""
    send_handoff_email(
        query_id=state.get("query_id", "unknown"),
        question=state["question"],
        answer=state["draft_answer"],
        faithfulness=state["faithfulness"],
        relevance=state["relevance"],
        confidence=state["confidence"],
    )
    return {
        "escalated": True,
        "draft_answer": (
            "We were unable to confidently answer this question from the paper. "
            "A researcher has been notified to review it."
        ),
    }


def complete_node(state: QueryState) -> dict:
    """Terminal node: decide needs_clarification for the low-but-passing case."""
    needs_clarification = state["confidence"] < 0.6
    clarification_prompt = None
    if needs_clarification:
        clarification_prompt = (
            "Could you clarify or narrow your question? The answer may be incomplete."
        )
    return {
        "needs_clarification": needs_clarification,
        "clarification_prompt": clarification_prompt,
        "escalated": False,
    }


def build_graph(checkpointer=None):
    """
    Build and compile the query graph.
    """
    builder = StateGraph(QueryState)

    builder.add_node("manager", manager_node)
    builder.add_node("specialist", specialist_node)
    builder.add_node("reflection", reflection_node)
    builder.add_node("escalate", escalate_node)
    builder.add_node("complete", complete_node)

    builder.set_entry_point("manager")
    builder.add_edge("manager", "specialist")
    builder.add_edge("specialist", "reflection")

    builder.add_conditional_edges(
        "reflection",
        should_continue,
        {
            "retry": "specialist",
            "escalate": "escalate",
            "complete": "complete",
        },
    )

    builder.add_edge("escalate", END)
    builder.add_edge("complete", END)

    if checkpointer is None:
        checkpointer = MemorySaver()
        
    return builder.compile(checkpointer=checkpointer)
