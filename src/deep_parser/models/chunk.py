"""Chunk model for storing document text chunks."""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

if TYPE_CHECKING:
    from .document import Document
    from .embedding import Embedding


class ChunkType(str, Enum):
    """Enumeration of chunk types."""
    ORIGINAL = "original"
    SUMMARY = "summary"


class EmbeddingStatus(str, Enum):
    """Enumeration of embedding processing status."""
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class Chunk(Base):
    """
    Chunk model representing text chunks from documents.
    
    Attributes:
        chunk_id: Primary key UUID
        doc_id: Foreign key to documents table
        chunk_type: Type of chunk (original or summary)
        level: Chunk hierarchy level
        window_size: Window size for chunking
        order_index: Order index in the document
        content: Chunk text content
        token_count: Token count of the content
        keywords: Extracted keywords as JSON
        qas: Question-answer pairs as JSON
        embedding_status: Embedding processing status
        created_at: Creation timestamp
        document: Related document
        embedding: Related embedding record
    """
    __tablename__ = "chunks"

    chunk_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4())
    )
    doc_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True
    )
    chunk_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    keywords: Mapped[list | None] = mapped_column(MySQLJSON, nullable=True)
    qas: Mapped[list | None] = mapped_column(MySQLJSON, nullable=True)
    embedding_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=EmbeddingStatus.PENDING.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="chunks"
    )
    embedding: Mapped["Embedding"] = relationship(
        "Embedding",
        back_populates="chunk",
        uselist=False
    )
