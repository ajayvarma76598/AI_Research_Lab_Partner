import logging
import re
from langchain_core.messages import HumanMessage

from config import get_llm
from query.state import QueryState
from langfuse.decorators import observe
from langfuse import Langfuse

logger = logging.getLogger(__name__)

VALID_AGENTS = ["summarization", "comparison", "gap_finder", "knowledge_organizer"]
langfuse_client = Langfuse()


@observe(as_type="span", name="manager_node")
def manager_node(state: QueryState) -> dict:
    """
    LLM-based routing node, same structure as triage_node() in
    demo-1-document-triage-system: build prompt -> invoke -> validate -> fallback.
    """
    question = state["question"]
    llm = get_llm()

    lf_prompt = langfuse_client.get_prompt("manager_classifier")
    prompt = lf_prompt.compile(question=question)

    response = llm.complete(prompt)
    # Strip any conversational filler or punctuation using regex
    raw_text = response.text.strip().lower()
    classification = re.sub(r'[^a-z_]', '', raw_text)

    if classification not in VALID_AGENTS:
        logger.warning(f"Manager returned unexpected classification '{classification}', defaulting to 'summarization'")
        classification = "summarization"

    logger.info(f"Manager routed question to: {classification}")

    return {
        "agent_used": classification,
        "messages": [HumanMessage(content=question)],
    }
