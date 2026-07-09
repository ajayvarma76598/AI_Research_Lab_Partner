import logging
from fastapi import FastAPI

from config import initialize_services
from db.models import init_db
from db.checkpointer import init_checkpointer
from ingest.routes import router as ingest_router
from query.routes import router as query_router
from discovery.routes import router as discovery_router
from compare.routes import router as compare_router
from langfuse.llama_index import LlamaIndexInstrumentor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AI Research Lab Partner",
    description="Multi-agent research assistant - ingestion and query endpoints",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev, restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize Azure OpenAI, pgvector, and the metadata DB on startup."""
    logger.info("Starting API server...")
    initialize_services()
    init_db()
    init_checkpointer()
    LlamaIndexInstrumentor().start()
    logger.info("API server started successfully")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "AI Research Lab Partner"}


app.include_router(ingest_router, tags=["ingest"])
app.include_router(query_router, tags=["query"])
app.include_router(discovery_router, tags=["discovery"])
app.include_router(compare_router, tags=["compare"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
