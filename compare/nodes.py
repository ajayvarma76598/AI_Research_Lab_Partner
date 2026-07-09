import logging
from typing import Dict, Any
import os
from config import get_langchain_llm
from query.retrieval import retrieve_chunks
from compare.state import CompareState
from langfuse.decorators import observe, langfuse_context
from langfuse import Langfuse
from langchain_core.messages import AIMessage

langfuse_client = Langfuse()

logger = logging.getLogger(__name__)

@observe(as_type="span", name="retriever_node")
def retriever_node(state: CompareState) -> Dict[str, Any]:
    """Retrieve chunks across all requested document IDs."""
    question = state["question"]
    document_ids = state["document_ids"]
    all_chunks = []
    
    for doc_id in document_ids:
        chunks = retrieve_chunks(doc_id, question)
        # tag chunks with their source
        for c in chunks:
            if "source_doc" not in c:
                c["source_doc"] = doc_id
        all_chunks.extend(chunks)
        
    return {
        "retrieved_chunks": all_chunks,
        "iteration": state.get("iteration", 0) + 1,
        "citations_count": len(all_chunks)
    }

@observe(as_type="span", name="synthesizer_node")
def synthesizer_node(state: CompareState) -> Dict[str, Any]:
    """Draft an initial comparison based on retrieved context."""
    question = state["question"]
    chunks = state.get("retrieved_chunks", [])
    
    if not chunks:
        return {"draft_answer": "No relevant information found across the requested documents."}
        
    # Group context by document
    docs_context = {}
    for c in chunks:
        doc_id = c.get("source_doc", "unknown")
        if doc_id not in docs_context:
            docs_context[doc_id] = []
        docs_context[doc_id].append(f"[{c['chunk_id']}] {c['text']}")
        
    combined_context_parts = []
    for doc_id, c_list in docs_context.items():
        combined_context_parts.append(f"--- Document ID: {doc_id} ---\n" + "\n\n".join(c_list))
    
    combined_context = "\n\n".join(combined_context_parts)
    
    llm = get_langchain_llm()
    lf_prompt = langfuse_client.get_prompt("compare_synthesizer")
    prompt = lf_prompt.compile(question=question, context=combined_context) + "\n\nCRITICAL INSTRUCTION: You are a helpful, human-like research assistant. Always provide your final answer in a natural, conversational, and humanized tone."
    response = llm.invoke(prompt)
    draft_answer = response.content.strip()
    
    return {"draft_answer": draft_answer, "messages": [AIMessage(content=draft_answer)]}

@observe(as_type="span", name="critique_node")
def critique_node(state: CompareState) -> Dict[str, Any]:
    """Evaluate the draft answer for fairness, accuracy, and depth."""
    question = state["question"]
    draft_answer = state.get("draft_answer", "")
    document_ids = state["document_ids"]
    
    # If there is no real draft, just pass
    if "No relevant information" in draft_answer or "cannot answer" in draft_answer.lower():
        return {"is_satisfactory": True, "critique": "No context available to critique."}
        
    llm = get_langchain_llm()
    lf_prompt = langfuse_client.get_prompt("compare_critic")
    prompt = lf_prompt.compile(question=question, draft_answer=draft_answer, document_ids=str(document_ids))
    response = llm.invoke(prompt)
    text = response.content.strip()
    
    is_satisfactory = False
    if "SATISFACTORY: YES" in text.upper():
        is_satisfactory = True
        
    critique_text = text.split("CRITIQUE:")[-1].strip() if "CRITIQUE:" in text else text
    
    try:
        langfuse_context.score_current_trace(
            name="comparison_satisfactory", 
            value=1.0 if is_satisfactory else 0.0, 
            comment=critique_text
        )
    except Exception as e:
        logger.warning(f"Langfuse scoring failed in compare: {e}")
    
    return {
        "is_satisfactory": is_satisfactory,
        "critique": critique_text
    }

@observe(as_type="span", name="revision_node")
def revision_node(state: CompareState) -> Dict[str, Any]:
    """Revise the draft based on the critique."""
    question = state["question"]
    draft_answer = state["draft_answer"]
    critique = state["critique"]
    chunks = state.get("retrieved_chunks", [])
    
    # Group context by document for reference
    docs_context = {}
    for c in chunks:
        doc_id = c.get("source_doc", "unknown")
        if doc_id not in docs_context:
            docs_context[doc_id] = []
        docs_context[doc_id].append(f"[{c['chunk_id']}] {c['text']}")
        
    combined_context_parts = []
    for doc_id, c_list in docs_context.items():
        combined_context_parts.append(f"--- Document ID: {doc_id} ---\n" + "\n\n".join(c_list))
    combined_context = "\n\n".join(combined_context_parts)
    
    llm = get_langchain_llm()
    lf_prompt = langfuse_client.get_prompt("compare_revision")
    prompt = lf_prompt.compile(question=question, context=combined_context, draft_answer=draft_answer, critique=critique) + "\n\nCRITICAL INSTRUCTION: You are a helpful, human-like research assistant. Always provide your final answer in a natural, conversational, and humanized tone."
    response = llm.invoke(prompt)
    revised_answer = response.content.strip()
    
    return {
        "draft_answer": revised_answer,
        "iteration": state.get("iteration", 0) + 1,
        "messages": [AIMessage(content=revised_answer)]
    }
