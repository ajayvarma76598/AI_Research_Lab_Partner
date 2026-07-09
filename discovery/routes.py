import logging
import time
import hashlib
import json
from fastapi import APIRouter, HTTPException

from discovery.schemas import DiscoveryRequest, DiscoveryResponse, DiscoveredPaper
from discovery.client import search_arxiv
from langfuse.decorators import observe, langfuse_context
from db.models import get_session, DiscoveryCacheRecord
from observability.security import check_prompt_injection

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/discover", response_model=DiscoveryResponse)
@observe(as_type="trace")
def discover_literature(request: DiscoveryRequest):
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
            session.close()
            results = [DiscoveredPaper(**item) for item in cached.results_json]
            processing_time_sec = round(time.time() - start_time, 2)
            langfuse_context.update_current_trace(output={"results_count": len(results), "processing_time_sec": processing_time_sec, "cached": True})
            return DiscoveryResponse(results=results, processing_time_sec=processing_time_sec, cached=True)

        results = search_arxiv(query=request.query, limit=request.limit)
        
        # Save to cache
        cache_record = DiscoveryCacheRecord(
            query_hash=query_hash,
            results_json=[p.model_dump() for p in results]
        )
        session.add(cache_record)
        session.commit()
        session.close()
        
        processing_time_sec = round(time.time() - start_time, 2)
        langfuse_context.update_current_trace(output={"results_count": len(results), "processing_time_sec": processing_time_sec, "cached": False})
        return DiscoveryResponse(results=results, processing_time_sec=processing_time_sec, cached=False)
    except Exception as e:
        if 'session' in locals():
            session.close()
        logger.error(f"Discovery failed: {e}")
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")
