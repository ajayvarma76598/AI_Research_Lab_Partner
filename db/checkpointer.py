import os
import logging
from psycopg_pool import ConnectionPool, AsyncConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

logger = logging.getLogger(__name__)

_pool = None
_checkpointer = None
_async_pool = None
_async_checkpointer = None

def init_checkpointer():
    global _pool, _checkpointer
    db_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    
    logger.info("Initializing Postgres checkpointer...")
    try:
        _pool = ConnectionPool(db_url, max_size=10, kwargs={"autocommit": True})
        _checkpointer = PostgresSaver(_pool)
        _checkpointer.setup()
        logger.info("Postgres checkpointer setup complete.")
    except Exception as e:
        logger.error(f"Failed to initialize checkpointer: {e}")
        raise

def get_checkpointer() -> PostgresSaver:
    if _checkpointer is None:
        init_checkpointer()
    return _checkpointer

def get_async_checkpointer() -> AsyncPostgresSaver:
    global _async_pool, _async_checkpointer
    if _async_checkpointer is None:
        db_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
        _async_pool = AsyncConnectionPool(db_url, max_size=10, kwargs={"autocommit": True})
        _async_checkpointer = AsyncPostgresSaver(_async_pool)
    return _async_checkpointer
