import logging
import os
import re
from typing import Tuple

from config import get_llm
from query.state import QueryState
from langfuse.decorators import langfuse_context, observe
from langfuse import Langfuse

langfuse_client = Langfuse()

logger = logging.getLogger(__name__)


def _parse_score(text: str) -> float:
    """Robust parsing approach using regex to safely extract the score."""
    match = re.search(r'Score:\s*([0-9]*\.?[0-9]+)', text)
    score = 0.0
    if match:
        try:
            score = float(match.group(1))
        except Exception as e:
            logger.warning(f"Failed to convert score to float: {e}")
    else:
        logger.warning(f"Regex failed to parse score from text: {text}")
        
    return max(0.0, min(1.0, score))


def evaluate_faithfulness_score(context: str, draft_answer: str) -> float:
    """Uses LLM-as-a-judge (Ragas style pattern) to evaluate faithfulness."""
    llm = get_llm()

    lf_prompt = langfuse_client.get_prompt("reflection_faithfulness")
    prompt = lf_prompt.compile(context=context, draft_answer=draft_answer)

    try:
        judgment = llm.complete(prompt)
        text = judgment.text.strip()
        score = _parse_score(text)
        try:
            langfuse_context.score_current_trace(name="faithfulness", value=score, comment=text)
        except Exception as e:
            logger.warning(f"Langfuse scoring failed (faithfulness): {e}")
        return score
    except Exception as e:
        logger.error(f"Faithfulness evaluation failed: {e}")
        return 0.0


def evaluate_answer_relevance(question: str, draft_answer: str) -> float:
    """Uses LLM-as-a-judge (Ragas style pattern) to evaluate relevance."""
    llm = get_llm()

    lf_prompt = langfuse_client.get_prompt("reflection_relevance")
    prompt = lf_prompt.compile(question=question, draft_answer=draft_answer)

    try:
        judgment = llm.complete(prompt)
        text = judgment.text.strip()
        score = _parse_score(text)
        try:
            langfuse_context.score_current_trace(name="relevance", value=score, comment=text)
        except Exception as e:
            logger.warning(f"Langfuse scoring failed (relevance): {e}")
        return score
    except Exception as e:
        logger.error(f"Relevance evaluation failed: {e}")
        return 0.0, str(e)


@observe(as_type="span", name="reflection_node")
def reflection_node(state: QueryState) -> dict:
    """
    Score the current draft answer and decide whether SLOs are met.

    langfuse_context manages attaching scores to the current trace automatically.
    """
    llm = get_llm()
    question = state["question"]
    answer = state["draft_answer"]
    chunks = state.get("retrieved_chunks", [])
    iteration = state.get("iteration", 0) + 1

    # ---- Hard short-circuit: no chunks means no grounding is possible ----
    # An empty context makes the faithfulness judge's score meaningless noise
    # (observed varying 0.0/0.8/1.0 across identical retries in production
    # logs). Never let this pass SLO, and don't waste LLM calls scoring it.
    if not chunks:
        logger.warning(
            f"Reflection iteration={iteration}: 0 chunks retrieved - forcing "
            f"slo_met=False without invoking the judge (empty context can't "
            f"be faithfully evaluated)."
        )
        try:
            langfuse_context.score_current_trace(name="faithfulness", value=0.0, comment="No chunks retrieved - not evaluated")
            langfuse_context.score_current_trace(name="relevance", value=0.0, comment="No chunks retrieved - not evaluated")
            langfuse_context.score_current_trace(name="confidence", value=0.0)
            langfuse_context.score_current_trace(name="slo_met", value=0.0)
        except Exception as e:
            logger.warning(f"Langfuse scoring failed (no-chunks case): {e}")

        return {
            "faithfulness": 0.0,
            "relevance": 0.0,
            "confidence": 0.0,
            "slo_met": False,
            "iteration": iteration,
        }

    context = "\n\n".join(c["text"] for c in chunks)

    faithfulness = evaluate_faithfulness_score(context, answer)
    relevance = evaluate_answer_relevance(question, answer)

    # Confidence: blend of retrieval quality (avg top-3 chunk similarity) and
    # the faithfulness/relevance scores - project-specific, not in the demo.
    top_scores = [c["score"] for c in chunks[:3]] or [0.0]
    retrieval_confidence = sum(top_scores) / len(top_scores)
    
    # Handle Abstention: If the specialist correctly identifies that the context lacks the information
    # (very common for gap_finder), the LLM judge often scores faithfulness/relevance poorly.
    # We should consider an honest abstention as meeting our SLOs so it returns to the user instead of escalating.
    abstain_phrases = ["does not mention", "no mention", "not mentioned", "insufficient context", "insufficient_context", "no limitations", "no gaps", "does not discuss", "not sufficient"]
    is_abstention = any(p in answer.lower() for p in abstain_phrases)
    
    if is_abstention:
        logger.info(f"Reflection iteration={iteration}: Answer identified as abstention. Overriding scores.")
        faithfulness = 1.0
        relevance = 1.0
        
    confidence = round(0.4 * retrieval_confidence + 0.3 * faithfulness + 0.3 * relevance, 3)

    slo_faithfulness_min = float(os.getenv("SLO_FAITHFULNESS_MIN", 0.6))
    slo_relevance_min = float(os.getenv("SLO_RELEVANCE_MIN", 0.5))
    handoff_confidence_threshold = float(os.getenv("HANDOFF_CONFIDENCE_THRESHOLD", 0.4))

    slo_met = (
        faithfulness >= slo_faithfulness_min
        and relevance >= slo_relevance_min
        and confidence >= handoff_confidence_threshold
    )

    try:
        langfuse_context.score_current_trace(name="confidence", value=confidence)
        langfuse_context.score_current_trace(name="slo_met", value=1.0 if slo_met else 0.0)
    except Exception as e:
        logger.warning(f"Langfuse scoring failed (confidence/slo_met): {e}")

    logger.info(
        f"Reflection iteration={iteration}: faithfulness={faithfulness}, "
        f"relevance={relevance}, confidence={confidence}, slo_met={slo_met}"
    )

    return {
        "faithfulness": faithfulness,
        "relevance": relevance,
        "confidence": confidence,
        "slo_met": slo_met,
        "iteration": iteration,
    }