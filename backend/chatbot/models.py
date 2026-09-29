from sqlalchemy import Integer, String, Text, ForeignKey, func, DateTime, Boolean, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, List, Dict, Any
from pgvector.sqlalchemy import Vector
from backend.core.database import Base

class ChatThread(Base):
    __tablename__ = "chat_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key = True)
    thread_id: Mapped[str] = mapped_column(String(50), unique = True, nullable = False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),nullable = False)
    preview:Mapped[str] = mapped_column(String(255), default = "New Conversation", server_default = "New Conversation")
    intent: Mapped[str] = mapped_column(String(50), default = "Diabetes")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default = func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default = func.now(), onupdate = func.now())
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates = "thread",
        cascade = "all, delete-orphan",
    )

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key = True)
    thread_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat_threads.id", ondelete = "CASCADE"),nullable = False)
    role: Mapped[str] = mapped_column(Text, nullable = False)
    content: Mapped[str] = mapped_column(Text, nullable = False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default = func.now())
    thread: Mapped[ChatThread] = relationship("ChatThread", back_populates = "messages")

class PrecomputedQA(Base):
    __tablename__ = "precomputed_qa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="Diabetes Diagnosis & Management")
    sources: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    embedding: Mapped[List[float]] = mapped_column(JSON, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    char_length: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    embedding: Mapped[List[float]] = mapped_column(Vector(768), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index(
            "idx_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )