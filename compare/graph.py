import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from compare.state import CompareState
from compare.nodes import retriever_node, synthesizer_node, critique_node, revision_node

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3

def should_continue(state: CompareState) -> str:
    """Determine if we should revise or finish."""
    if state.get("is_satisfactory"):
        logger.info("CRITIC: Comparison is satisfactory. Finishing.")
        return "complete"
        
    if state.get("iteration", 0) >= MAX_ITERATIONS:
        logger.warning(f"CRITIC: Max iterations reached. Finishing with current draft.")
        return "complete"
        
    logger.info(f"CRITIC: Comparison rejected. Revising. (Iteration {state.get('iteration', 0)})")
    return "revise"

def build_compare_graph(checkpointer=None):
    builder = StateGraph(CompareState)
    
    builder.add_node("retriever", retriever_node)
    builder.add_node("synthesizer", synthesizer_node)
    builder.add_node("critique", critique_node)
    builder.add_node("revision", revision_node)
    
    builder.set_entry_point("retriever")
    builder.add_edge("retriever", "synthesizer")
    builder.add_edge("synthesizer", "critique")
    
    builder.add_conditional_edges(
        "critique",
        should_continue,
        {
            "revise": "revision",
            "complete": END
        }
    )
    
    builder.add_edge("revision", "critique")
    
    if checkpointer is None:
        checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)
