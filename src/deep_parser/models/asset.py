"""Asset model for storing document-related assets like images."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

if TYPE_CHECKING:
    from .document import Document


class Asset(Base):
    """
    Asset model representing document assets (images, videos, etc.).
    
    Attributes:
        asset_id: Primary key UUID
        doc_id: Foreign key to documents table
        orig_path: Original asset path
        mime_type: MIME type of the asset
        size: Asset size in bytes
        image_host_url: Hosted image URL
        created_at: Creation timestamp
        document: Related document
    """
    __tablename__ = "assets"

    asset_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4())
    )
    doc_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True
    )
    orig_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    image_host_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="assets"
    )
