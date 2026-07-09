import logging
import os
from langchain_core.messages import HumanMessage, AIMessage
from config import get_langchain_llm
from query.state import QueryState
from query.retrieval import retrieve_chunks
from langfuse.decorators import observe
from langfuse import Langfuse

langfuse_client = Langfuse()

logger = logging.getLogger(__name__)

AGENT_PROMPTS = {
    "summarization": "Summarize the key contributions and findings relevant to the question. Be extremely concise.",
    "comparison": "Compare the methods/approaches discussed, highlighting differences and tradeoffs. Be extremely concise.",
    "gap_finder": """You are an expert research analyst.

Given the retrieved context, identify any of the following:

- Explicit limitations
- Future research directions
- Open research questions
- Unresolved challenges

Be extremely concise and direct in your response. Do not use filler words.
- Research gaps acknowledged by the authors

Rules:
- Base every statement ONLY on the provided context.
- Never invent or infer gaps that are not supported by the context.
- Do not summarize the paper.
- Do not discuss methodology unless it is presented as a limitation.
- Return concise bullet points.
- If no such information exists in the context, return exactly:

INSUFFICIENT_CONTEXT.""",
    "knowledge_organizer": "Organize the relevant findings into clear, structured notes.",
}


@observe(as_type="span", name="specialist_node")
def specialist_node(state: QueryState) -> dict:
    """
    Retrieve document_id-scoped chunks and generate a grounded draft answer.

    Guardrail: the LLM is explicitly instructed to answer ONLY from the
    provided context and to say so plainly if the context is insufficient -
    this is the guardrail/grounding design pattern from our project plan.
    """
    question = state["question"]
    document_id = state["document_id"]
    agent_used = state["agent_used"]
    
    # Query Expansion: Use a highly descriptive natural language query 
    # instead of keyword soup, because dense embedding models (like OpenAI) 
    # perform much better on well-formed sentences.
    search_query = question
    if agent_used == "gap_finder":
        search_query = "What are the explicit limitations, research gaps, future work, unresolved challenges, and open questions discussed in this document?"

    chunks = retrieve_chunks(document_id, search_query)
    
    # Debug logging for retrieved chunks
    logger.info(f"--- Retrieved {len(chunks)} Chunks for agent '{agent_used}' ---")
    for i, c in enumerate(chunks):
        logger.info(f"Chunk {i+1} [score={c.get('score', 0):.3f}]:\n{c['text']}\n" + "-"*40)
        
    context = "\n\n".join(f"[{c['chunk_id']}] {c['text']}" for c in chunks)

    role_instruction = AGENT_PROMPTS.get(agent_used, AGENT_PROMPTS["summarization"])

    lf_prompt = langfuse_client.get_prompt("specialist_generator")
    prompt = lf_prompt.compile(
        role_instruction=role_instruction,
        context=context,
        question=question
    ) + "\n\nCRITICAL INSTRUCTION: You are a helpful, human-like research assistant. Always provide your final answer in a natural, conversational, and humanized tone."

    llm = get_langchain_llm()
    
    # Use standard invoke. LangGraph astream_events will capture the stream chunks automatically 
    # since this is a langchain chat model.
    response = llm.invoke(prompt)
    draft_answer = response.content.strip()

    logger.info(f"Specialist ({agent_used}) drafted answer, iteration={state.get('iteration', 0)}")
    logger.info(f"Draft Answer: {draft_answer}")

    return {
        "draft_answer": draft_answer,
        "retrieved_chunks": chunks,
        "messages": [AIMessage(content=draft_answer)],
    }
