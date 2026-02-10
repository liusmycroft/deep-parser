"""Embedding model for storing vector embedding metadata."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

if TYPE_CHECKING:
    from .chunk import Chunk


class Embedding(Base):
    """
    Embedding model representing vector embedding metadata.
    
    Attributes:
        chunk_id: Primary key and foreign key to chunks table
        embedding_model: Name of the embedding model used
        dim: Dimension of the embedding vector
        vector_ref: Reference to vector storage (Milvus/CH/ES)
        created_at: Creation timestamp
        chunk: Related chunk
    """
    __tablename__ = "embeddings"

    chunk_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True
    )
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    vector_ref: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    chunk: Mapped["Chunk"] = relationship(
        "Chunk",
        back_populates="embedding"
    )
