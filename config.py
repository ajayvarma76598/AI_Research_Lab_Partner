import os
import logging
from typing import Optional
from dotenv import load_dotenv

from llama_index.core import Settings
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from llama_index.vector_stores.postgres import PGVectorStore

from langchain_openai import AzureChatOpenAI

logger = logging.getLogger(__name__)
load_dotenv()

# ============================================================================
# Required environment variables
# (same validation pattern as demo-2-semantic-chunking-rag/rag-service.py)
# ============================================================================
REQUIRED_VARS = [
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_LLM_DEPLOYMENT",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_TABLE_NAME",
]


def validate_env():
    missing = [v for v in REQUIRED_VARS if not os.getenv(v)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    logger.info("Environment variables validated")


# ============================================================================
# Global singletons (populated by initialize_services())
# ============================================================================
_llm: Optional[AzureOpenAI] = None
_langchain_llm: Optional[AzureChatOpenAI] = None
_embed_model: Optional[AzureOpenAIEmbedding] = None
_vector_store: Optional[PGVectorStore] = None
_initialized = False


def initialize_services():
    """Initialize Azure OpenAI LLM/embeddings and the pgvector store.

    Mirrors demo-2-semantic-chunking-rag/rag-service.py: initialize_services().
    """
    global _llm, _langchain_llm, _embed_model, _vector_store, _initialized

    if _initialized:
        logger.info("Services already initialized, reusing existing instances")
        return

    validate_env()

    logger.info("Initializing Azure OpenAI services...")
    _llm = AzureOpenAI(
        model=os.getenv("AZURE_OPENAI_LLM_MODEL", "gpt-4o-mini"),
        deployment_name=os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
        max_tokens=256,
        system_prompt="You are a helpful, human-like research assistant. Always provide answers in a natural, conversational, and humanized tone."
    )

    _embed_model = AzureOpenAIEmbedding(
        model=os.getenv("AZURE_OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        deployment_name=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
    )

    _langchain_llm = AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
        temperature=0,
        max_tokens=256
    )

    # Assign to global Settings (same pattern as demo-2-semantic-chunking-rag)
    Settings.llm = _llm
    Settings.embed_model = _embed_model

    # PGVectorStore - same as demo-1-table-extraction / demo-3-unified-multimodal
    _vector_store = PGVectorStore.from_params(
        database=os.getenv("DB_NAME"),
        host=os.getenv("DB_HOST"),
        password=os.getenv("DB_PASSWORD"),
        port=int(os.getenv("DB_PORT", 5432)),
        user=os.getenv("DB_USER"),
        table_name=os.getenv("DB_TABLE_NAME"),
        embed_dim=1536,  # text-embedding-3-small dimension
    )

    _initialized = True
    logger.info("All services initialized successfully")


def get_llm() -> AzureOpenAI:
    if not _initialized:
        initialize_services()
    return _llm


def get_embed_model() -> AzureOpenAIEmbedding:
    if not _initialized:
        initialize_services()
    return _embed_model


def get_vector_store() -> PGVectorStore:
    if not _initialized:
        initialize_services()
    return _vector_store

def get_langchain_llm() -> AzureChatOpenAI:
    if not _initialized:
        initialize_services()
    return _langchain_llm
