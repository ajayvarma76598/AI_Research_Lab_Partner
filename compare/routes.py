import logging
import uuid
import time
import hashlib
import json
import asyncio
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from models.schemas import CompareRequest, CompareResponse, Citation
from auth.jwt import get_current_user, User
from langfuse.decorators import observe, langfuse_context
from compare.graph import build_compare_graph
from db.models import get_session, QueryCacheRecord, ChatSession
from db.checkpointer import get_checkpointer, get_async_checkpointer
from langchain_core.messages import HumanMessage
from observability.security import check_prompt_injection

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/compare", response_model=CompareResponse)
@observe(as_type="trace")
def compare_documents(request: CompareRequest, user: User = Depends(get_current_user)):
    start_time = time.time()
    query_id = f"cmp_{uuid.uuid4().hex[:8]}"

    langfuse_context.update_current_trace(
        name="compare",
        input={"document_ids": request.document_ids, "question": request.question},
    )

    if check_prompt_injection(request.question):
        raise HTTPException(status_code=403, detail="Blocked by Prompt Injection Firewall")

    query_hash = hashlib.sha256(f"{sorted(request.document_ids)}_{request.question}".encode()).hexdigest()
    
    session = get_session()
    cached = session.query(QueryCacheRecord).filter_by(query_hash=query_hash).first()
    if cached:
        logger.info(f"Cache HIT for compare query '{request.question}'. Retrieving from QueryCacheRecord.")
        session.close()
        response_data = cached.response_json
        processing_time_sec = round(time.time() - start_time, 2)
        response_data["processing_time_sec"] = processing_time_sec
        response_data["cached"] = True
        response_data["query_id"] = query_id # Assign new query id for this request
        langfuse_context.update_current_trace(output=response_data)
        return CompareResponse(**response_data)

    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    db_session = session.query(ChatSession).filter_by(thread_id=thread_id).first()
    if not db_session:
        new_chat = ChatSession(thread_id=thread_id, user_id=user.user_id, document_id=None, title="Comparison")
        session.add(new_chat)
        session.commit()
    
    graph = build_compare_graph(get_checkpointer())
    
    initial_state = {
        "query_id": query_id,
        "document_ids": request.document_ids,
        "question": request.question,
        "retrieved_chunks": [],
        "draft_answer": "",
        "critique": "",
        "is_satisfactory": False,
        "iteration": 0,
        "citations_count": 0,
        "messages": [HumanMessage(content=request.question)]
    }
    
    try:
        config = {"configurable": {"thread_id": query_id}}
        result = graph.invoke(initial_state, config)
    except Exception as e:
        logger.error(f"Compare graph execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")

    answer = result.get("draft_answer", "Error generating comparison.")
    
    citations = [
        Citation(chunk_id=c["chunk_id"], page=c.get("page"), snippet_ref=c.get("chunk_type"))
        for c in result.get("retrieved_chunks", [])
    ]
    
    processing_time_sec = round(time.time() - start_time, 2)

    langfuse_context.update_current_trace(output={
        "answer": answer,
        "citations_count": len(citations),
        "iterations": result.get("iteration", 0),
        "processing_time_sec": processing_time_sec
    })

    response = CompareResponse(
        query_id=query_id,
        answer=answer,
        citations=citations,
        processing_time_sec=processing_time_sec,
        thread_id=thread_id,
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

@router.post("/compare/stream")
@observe(as_type="trace")
async def compare_documents_stream(request: CompareRequest, user: User = Depends(get_current_user)):
    start_time = time.time()
    query_id = f"cmp_{uuid.uuid4().hex[:8]}"

    langfuse_context.update_current_trace(
        name="compare_stream",
        input={"document_ids": request.document_ids, "question": request.question},
    )

    if check_prompt_injection(request.question):
        raise HTTPException(status_code=403, detail="Blocked by Prompt Injection Firewall")

    query_hash = hashlib.sha256(f"{sorted(request.document_ids)}_{request.question}".encode()).hexdigest()
    
    session = get_session()
    cached = session.query(QueryCacheRecord).filter_by(query_hash=query_hash).first()
    if cached:
        logger.info(f"Cache HIT for compare stream '{request.question}'. Retrieving from QueryCacheRecord.")
        session.close()
        response_data = cached.response_json
        processing_time_sec = round(time.time() - start_time, 2)
        response_data["processing_time_sec"] = processing_time_sec
        response_data["cached"] = True
        response_data["query_id"] = query_id
        
        async def cached_stream():
            answer = response_data.get('answer', '')
            chunk_size = 20
            for i in range(0, len(answer), chunk_size):
                yield f"event: message\ndata: {json.dumps({'content': answer[i:i+chunk_size]})}\n\n"
                await asyncio.sleep(0.01)
            yield f"event: metadata\ndata: {json.dumps(response_data)}\n\n"
        
        return StreamingResponse(cached_stream(), media_type="text/event-stream")

    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    db_session = session.query(ChatSession).filter_by(thread_id=thread_id).first()
    if not db_session:
        new_chat = ChatSession(thread_id=thread_id, user_id=user.user_id, document_id=None, title="Comparison")
        session.add(new_chat)
        session.commit()

    graph = build_compare_graph(get_async_checkpointer())
    
    initial_state = {
        "query_id": query_id,
        "document_ids": request.document_ids,
        "question": request.question,
        "retrieved_chunks": [],
        "draft_answer": "",
        "critique": "",
        "is_satisfactory": False,
        "iteration": 0,
        "citations_count": 0,
        "messages": [HumanMessage(content=request.question)]
    }
    
    
    async def event_generator():
        try:
            # Run the complex actor-critic loop completely in the background
            # so we don't stream intermediate drafts or critic thoughts to the frontend
            final_state = await graph.ainvoke(initial_state, config)
            
            answer = final_state.get("draft_answer", "Error generating comparison.")
            citations = [
                Citation(chunk_id=c["chunk_id"], page=c.get("page"), snippet_ref=c.get("chunk_type")).model_dump()
                for c in final_state.get("retrieved_chunks", [])
            ]
            processing_time_sec = round(time.time() - start_time, 2)
            
            metadata = {
                "query_id": query_id,
                "answer": answer,
                "citations": citations,
                "thread_id": thread_id,
                "processing_time_sec": processing_time_sec,
                "cached": False,
            }
            
            cache_record = QueryCacheRecord(
                query_hash=query_hash,
                response_json=metadata
            )
            session.add(cache_record)
            session.commit()
            
            # Now simulate streaming the final polished answer to the frontend
            chunk_size = 20
            for i in range(0, len(answer), chunk_size):
                yield f"event: message\ndata: {json.dumps({'content': answer[i:i+chunk_size]})}\n\n"
                await asyncio.sleep(0.01)
                
            yield f"event: metadata\ndata: {json.dumps(metadata)}\n\n"
            
        except Exception as e:
            logger.error(f"Compare streaming failed: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
        finally:
            session.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
