import logging
import time
import hashlib
import json
from fastapi import APIRouter, HTTPException, Depends

from discovery.schemas import DiscoveryRequest, DiscoveryResponse, DiscoveredPaper
from discovery.client import search_arxiv
from langfuse.decorators import observe, langfuse_context
from db.models import get_session, DiscoveryCacheRecord, ChatSession
from observability.security import check_prompt_injection
from auth.jwt import get_current_user, User
import uuid
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
from db.checkpointer import get_checkpointer

class DiscoveryState(TypedDict):
    messages: Annotated[list, add_messages]

def empty_node(state):
    return {}

def save_discovery_history(query, results, thread_id, user_id, session):
    db_session = session.query(ChatSession).filter_by(thread_id=thread_id).first()
    if not db_session:
        new_chat = ChatSession(thread_id=thread_id, user_id=user_id, document_id=None, title="Discovery Search")
        session.add(new_chat)
        session.commit()
    
    answer = f"I found {len(results)} papers related to your query:\n\n"
    for i, paper in enumerate(results):
        answer += f"**{i+1}. {paper.title}**\n"
        answer += f"*Authors: {', '.join(paper.authors)}*\n"
        if paper.pdf_url:
            answer += f"[Read PDF]({paper.pdf_url})\n"
        answer += "\n"
    
    builder = StateGraph(DiscoveryState)
    builder.add_node("node", empty_node)
    builder.set_entry_point("node")
    builder.add_edge("node", END)
    graph = builder.compile(checkpointer=get_checkpointer())
    
    graph.invoke(
        {"messages": [HumanMessage(content=query), AIMessage(content=answer)]},
        config={"configurable": {"thread_id": thread_id}}
    )

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/discover", response_model=DiscoveryResponse)
@observe(as_type="trace")
def discover_literature(request: DiscoveryRequest, user: User = Depends(get_current_user)):
    """Discover scientific literature using ArXiv API."""
    start_time = time.time()
    langfuse_context.update_current_trace(name="discover", input={"query": request.query, "limit": request.limit})

    if check_prompt_injection(request.query):
        raise HTTPException(status_code=403, detail="Blocked by Prompt Injection Firewall")

    try:
        query_hash = hashlib.sha256(f"{request.query}_{request.limit}".encode()).hexdigest()
        
        session = get_session()
        cached = session.query(DiscoveryCacheRecord).filter_by(query_hash=query_hash).first()
        if cached:
            logger.info(f"Cache HIT for discovery query '{request.query}'. Retrieving from DiscoveryCacheRecord.")
            session.close()
            results = [DiscoveredPaper(**item) for item in cached.results_json]
            
            thread_id = request.thread_id or str(uuid.uuid4())
            save_discovery_history(request.query, results, thread_id, user.user_id, session)
            
            processing_time_sec = round(time.time() - start_time, 2)
            langfuse_context.update_current_trace(output={"results_count": len(results), "processing_time_sec": processing_time_sec, "cached": True})
            return DiscoveryResponse(results=results, processing_time_sec=processing_time_sec, thread_id=thread_id, cached=True)

        results = search_arxiv(query=request.query, limit=request.limit)
        
        # Save to cache
        cache_record = DiscoveryCacheRecord(
            query_hash=query_hash,
            results_json=[p.model_dump() for p in results]
        )
        session.add(cache_record)
        session.commit()
        thread_id = request.thread_id or str(uuid.uuid4())
        save_discovery_history(request.query, results, thread_id, user.user_id, session)
        
        session.close()
        
        processing_time_sec = round(time.time() - start_time, 2)
        langfuse_context.update_current_trace(output={"results_count": len(results), "processing_time_sec": processing_time_sec, "cached": False})
        return DiscoveryResponse(results=results, processing_time_sec=processing_time_sec, thread_id=thread_id, cached=False)
    except Exception as e:
        if 'session' in locals():
            session.close()
        logger.error(f"Discovery failed: {e}")
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")
