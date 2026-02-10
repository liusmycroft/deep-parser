"""Document model for storing source document metadata."""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

if TYPE_CHECKING:
    from .asset import Asset
    from .chunk import Chunk


class SourceType(str, Enum):
    """Enumeration of document source types."""
    WECHAT = "wechat"
    ZHIHU = "zhihu"
    MANUAL = "manual"


class DocumentStatus(str, Enum):
    """Enumeration of document processing status."""
    UPLOADED = "uploaded"
    CLEANED = "cleaned"
    SPLITTED = "splitted"
    INDEXED = "indexed"
    FAILED = "failed"


class Document(Base):
    """
    Document model representing source documents.
    
    Attributes:
        doc_id: Primary key UUID
        source_type: Type of document source
        title: Document title
        author: Document author
        published_at: Publication timestamp
        raw_storage_path: Path to raw document storage
        cleaned_markdown_path: Path to cleaned markdown
        status: Processing status
        created_at: Creation timestamp
        updated_at: Last update timestamp
        error_message: Error message if processing failed
        assets: Related asset records
        chunks: Related chunk records
    """
    __tablename__ = "documents"

    doc_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4())
    )
    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    raw_storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_markdown_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=DocumentStatus.UPLOADED.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    assets: Mapped[list["Asset"]] = relationship(
        "Asset",
        back_populates="document",
        cascade="all, delete-orphan"
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )
