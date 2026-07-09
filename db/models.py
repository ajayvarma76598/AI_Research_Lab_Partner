"""
SQLAlchemy models for document metadata and idempotency tracking.

Not directly from a single demo file (your demos relied on LlamaIndex's
PGVectorStore for the vector data itself). This adds a small side table so
/ingest/document can:
  - check file_hash to avoid re-processing the same PDF (idempotency)
  - store structured metadata (title, authors, citation_count) queryable
    outside of the vector store
"""
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
from sqlalchemy import create_engine, Column, String, Integer, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy import ForeignKey

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True)  # From Auth0 / OAuth sub
    email = Column(String, unique=True, index=True)
    name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    sessions = relationship("ChatSession", back_populates="user")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    thread_id = Column(String, primary_key=True) # Matches LangGraph thread_id
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    document_id = Column(String, ForeignKey("documents.document_id"), nullable=False)
    title = Column(String, default="New Chat")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="sessions")
    document = relationship("DocumentRecord")


class DocumentRecord(Base):
    __tablename__ = "documents"

    document_id = Column(String, primary_key=True)
    file_hash = Column(String, unique=True, index=True, nullable=False)
    title = Column(String)
    source_filename = Column(String)
    metadata_json = Column(JSON, default=dict)
    chunks_indexed = Column(Integer, default=0)
    chunks_failed = Column(Integer, default=0)
    tables_processed = Column(Integer, default=0)
    figures_processed = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class DiscoveryCacheRecord(Base):
    __tablename__ = "discovery_cache"

    query_hash = Column(String, primary_key=True)
    results_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class QueryCacheRecord(Base):
    __tablename__ = "query_cache"

    query_hash = Column(String, primary_key=True)
    response_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


def get_engine():
    db_url = (
        f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )
    logger.info(f"Creating database engine")
    return create_engine(db_url)


_engine = None
_SessionLocal = None


def init_db():
    global _engine, _SessionLocal
    try:
        _engine = get_engine()
        logger.info("Initializing database schema...")
        Base.metadata.create_all(_engine)
        _SessionLocal = sessionmaker(bind=_engine)
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database connection: {e}")
        raise


def get_session():
    if _SessionLocal is None:
        init_db()
    return _SessionLocal()
