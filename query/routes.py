import logging
import uuid
import time
import hashlib
import json
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from models.schemas import QueryRequest, QueryResponse, Citation
from auth.jwt import get_current_user, User
from langfuse.decorators import observe, langfuse_context
from query.graph import build_graph
from db.models import get_session, QueryCacheRecord, ChatSession, DocumentRecord
from db.checkpointer import get_checkpointer, get_async_checkpointer
from observability.security import check_prompt_injection

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse)
@observe(as_type="trace")
def query_document(request: QueryRequest, user: User = Depends(get_current_user)):
    start_time = time.time()
    query_id = f"q_{uuid.uuid4().hex[:8]}"

    langfuse_context.update_current_trace(
        name="query",
        input={"document_id": request.document_id, "question": request.question},
    )

    if check_prompt_injection(request.question):
        raise HTTPException(status_code=403, detail="Blocked by Prompt Injection Firewall")

    query_hash = hashlib.sha256(f"{request.document_id}_{request.question}".encode()).hexdigest()
    
    session = get_session()
    cached = session.query(QueryCacheRecord).filter_by(query_hash=query_hash).first()
    if cached:
        session.close()
        response_data = cached.response_json
        processing_time_sec = round(time.time() - start_time, 2)
        response_data["processing_time_sec"] = processing_time_sec
        response_data["cached"] = True
        response_data["query_id"] = query_id # Assign new query id for this request
        langfuse_context.update_current_trace(output=response_data)
        return QueryResponse(**response_data)

    # Same thread_id pattern as demo-3-multi-turn-support-agent/main.py:
    # auto-generate if not provided, so the client can use it for follow-ups.
    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # Track ChatSession in our relational DB to list in the UI later
    db_session = session.query(ChatSession).filter_by(thread_id=thread_id).first()
    if not db_session:
        doc = session.query(DocumentRecord).filter_by(document_id=request.document_id).first()
        title = doc.title if doc else "New Chat"
        new_chat = ChatSession(thread_id=thread_id, user_id=user.user_id, document_id=request.document_id, title=title)
        session.add(new_chat)
        session.commit()

    graph = build_graph(get_checkpointer())

    initial_state = {
        "user_id": user.user_id, # Track who owns this query
        "document_id": request.document_id,
        "question": request.question,
        "agent_used": "",
        "retrieved_chunks": [],
        "draft_answer": "",
        "faithfulness": 0.0,
        "relevance": 0.0,
        "confidence": 0.0,
        "iteration": 0,
        "needs_clarification": False,
        "clarification_prompt": None,
        "escalated": False,
        "slo_met": False,
        "messages": [],
    }

    try:
        result = graph.invoke(initial_state, config)
    except Exception as e:
        logger.error(f"Query graph execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")

    citations = [
        Citation(chunk_id=c["chunk_id"], page=c.get("page"), snippet_ref=c.get("chunk_type"))
        for c in result.get("retrieved_chunks", [])
    ]

    processing_time_sec = round(time.time() - start_time, 2)

    langfuse_context.update_current_trace(output={
        "answer": result["draft_answer"],
        "confidence": result["confidence"],
        "escalated": result["escalated"],
        "processing_time_sec": processing_time_sec
    })

    final_answer = result["draft_answer"]
    if "INSUFFICIENT_CONTEXT" in final_answer:
        final_answer = "I couldn't find any information about this in the provided text."

    response = QueryResponse(
        query_id=query_id,
        answer=final_answer,
        citations=citations,
        confidence=result["confidence"],
        faithfulness=result["faithfulness"],
        relevance=result["relevance"],
        agent_used=result["agent_used"],
        needs_clarification=result["needs_clarification"],
        clarification_prompt=result["clarification_prompt"],
        escalated=result["escalated"],
        thread_id=thread_id,
        processing_time_sec=processing_time_sec,
        cached=False,
    )
    
    # Save to cache
    cache_record = QueryCacheRecord(
        query_hash=query_hash,
        response_json=response.model_dump()
    )
    session.add(cache_record)
    session.commit()
    session.close()

    return response

@router.post("/query/stream")
@observe(as_type="trace")
async def query_document_stream(request: QueryRequest, user: User = Depends(get_current_user)):
    start_time = time.time()
    query_id = f"q_{uuid.uuid4().hex[:8]}"

    langfuse_context.update_current_trace(
        name="query_stream",
        input={"document_id": request.document_id, "question": request.question},
    )

    if check_prompt_injection(request.question):
        raise HTTPException(status_code=403, detail="Blocked by Prompt Injection Firewall")

    query_hash = hashlib.sha256(f"{request.document_id}_{request.question}".encode()).hexdigest()
    
    session = get_session()
    cached = session.query(QueryCacheRecord).filter_by(query_hash=query_hash).first()
    if cached:
        session.close()
        response_data = cached.response_json
        processing_time_sec = round(time.time() - start_time, 2)
        response_data["processing_time_sec"] = processing_time_sec
        response_data["cached"] = True
        response_data["query_id"] = query_id
        
        async def cached_stream():
            yield f"event: message\ndata: {json.dumps({'content': response_data['answer']})}\n\n"
            yield f"event: metadata\ndata: {json.dumps(response_data)}\n\n"
        
        return StreamingResponse(cached_stream(), media_type="text/event-stream")

    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    db_session = session.query(ChatSession).filter_by(thread_id=thread_id).first()
    if not db_session:
        doc = session.query(DocumentRecord).filter_by(document_id=request.document_id).first()
        title = doc.title if doc else "New Chat"
        new_chat = ChatSession(thread_id=thread_id, user_id=user.user_id, document_id=request.document_id, title=title)
        session.add(new_chat)
        session.commit()

    graph = build_graph(get_async_checkpointer())

    initial_state = {
        "user_id": user.user_id,
        "document_id": request.document_id,
        "question": request.question,
        "agent_used": "",
        "retrieved_chunks": [],
        "draft_answer": "",
        "faithfulness": 0.0,
        "relevance": 0.0,
        "confidence": 0.0,
        "iteration": 0,
        "needs_clarification": False,
        "clarification_prompt": None,
        "escalated": False,
        "slo_met": False,
        "messages": [],
    }

    async def event_generator():
        try:
            final_state = None
            async for event in graph.astream_events(initial_state, config, version="v1"):
                kind = event["event"]
                
                # Stream LLM tokens to frontend
                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        yield f"event: message\ndata: {json.dumps({'content': chunk.content})}\n\n"
                
                # Capture the final state from the graph completion
                if kind == "on_chain_end" and event["name"] == "LangGraph":
                    final_state = event["data"]["output"]
            
            if final_state:
                citations = [
                    Citation(chunk_id=c["chunk_id"], page=c.get("page"), snippet_ref=c.get("chunk_type")).model_dump()
                    for c in final_state.get("retrieved_chunks", [])
                ]
                processing_time_sec = round(time.time() - start_time, 2)
                
                final_answer = final_state.get("draft_answer", "")
                if "INSUFFICIENT_CONTEXT" in final_answer:
                    final_answer = "I couldn't find any information about this in the provided text."
                
                metadata = {
                    "query_id": query_id,
                    "answer": final_answer,
                    "citations": citations,
                    "confidence": final_state.get("confidence", 0.0),
                    "faithfulness": final_state.get("faithfulness", 0.0),
                    "relevance": final_state.get("relevance", 0.0),
                    "agent_used": final_state.get("agent_used", ""),
                    "needs_clarification": final_state.get("needs_clarification", False),
                    "clarification_prompt": final_state.get("clarification_prompt", None),
                    "escalated": final_state.get("escalated", False),
                    "thread_id": thread_id,
                    "processing_time_sec": processing_time_sec,
                    "cached": False,
                }
                
                # Save to cache
                cache_record = QueryCacheRecord(
                    query_hash=query_hash,
                    response_json=metadata
                )
                session.add(cache_record)
                session.commit()
                
                yield f"event: metadata\ndata: {json.dumps(metadata)}\n\n"
                
        except Exception as e:
            logger.error(f"Streaming failed: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
        finally:
            session.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/sessions")
def get_user_sessions(user: User = Depends(get_current_user)):
    """Retrieve all chat sessions for the logged-in user."""
    session = get_session()
    try:
        sessions = session.query(ChatSession).filter_by(user_id=user.user_id).order_by(ChatSession.updated_at.desc()).all()
        return [
            {
                "thread_id": s.thread_id,
                "document_id": s.document_id,
                "title": s.title,
                "updated_at": s.updated_at.isoformat()
            } for s in sessions
        ]
    except Exception as e:
        logger.error(f"Failed to fetch sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch chat sessions")
    finally:
        session.close()

@router.get("/sessions/{thread_id}/history")
def get_session_history(thread_id: str, user: User = Depends(get_current_user)):
    """Retrieve conversation history for a specific thread."""
    session = get_session()
    try:
        # Validate ownership
        db_session = session.query(ChatSession).filter_by(thread_id=thread_id, user_id=user.user_id).first()
        if not db_session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        # Load messages from LangGraph Postgres checkpointer
        checkpointer = get_checkpointer()
        config = {"configurable": {"thread_id": thread_id}}
        state_tuple = checkpointer.get_tuple(config)
        
        if not state_tuple:
            return {"messages": []}
            
        # Parse standard langchain messages
        messages = []
        for msg in state_tuple.checkpoint.get("channel_values", {}).get("messages", []):
            messages.append({
                "role": msg.type,
                "content": msg.content
            })
            
        return {"messages": messages}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch chat history")
    finally:
        session.close()
