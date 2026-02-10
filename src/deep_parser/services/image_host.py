"""Image hosting service for managing image storage and access."""

import hashlib
from pathlib import Path
from typing import Optional

from deep_parser.config.settings import get_settings
from deep_parser.logging_config import logger


class ImageHostService:
    """Service for managing image hosting and deduplication."""

    def __init__(self, storage_base_path: str, base_url: str):
        """Initialize image host service.

        Args:
            storage_base_path: Base path for storage
            base_url: Base URL for image access
        """
        self.storage_base_path = Path(storage_base_path)
        self.base_url = base_url
        self._images_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"ImageHostService initialized with "
            f"storage_base_path: {self.storage_base_path}, "
            f"base_url: {self.base_url}"
        )

    @property
    def images_dir(self) -> Path:
        """Get the images directory path.

        Returns:
            Path to images directory
        """
        return self.storage_base_path / "images"

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file.

        Args:
            file_path: Path to file

        Returns:
            Hex string of SHA256 hash
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def upload_image(self, doc_id: str, image_path: Path) -> str:
        """Upload image to image host with deduplication.

        Args:
            doc_id: Document ID (for logging)
            image_path: Path to image file

        Returns:
            Hosted image URL
        """
        file_hash = self._calculate_file_hash(image_path)
        file_ext = image_path.suffix
        filename = f"{file_hash}{file_ext}"
        target_path = self.images_dir / filename

        if not target_path.exists():
            target_path.write_bytes(image_path.read_bytes())
            logger.info(
                f"Uploaded image for doc {doc_id}: {image_path.name} -> {filename}"
            )
        else:
            logger.info(
                f"Image already exists for doc {doc_id}: {filename} (deduped)"
            )

        return f"{self.base_url}/{filename}"

    def get_image_path(self, filename: str) -> Path:
        """Get local path for an image filename.

        Args:
            filename: Image filename

        Returns:
            Path to image file
        """
        return self.images_dir / filename


def get_image_host_service() -> ImageHostService:
    """Factory function to get image host service instance.

    Returns:
        ImageHostService instance configured from settings
    """
    settings = get_settings()
    return ImageHostService(
        storage_base_path=settings.storage_base_path,
        base_url=settings.image_host_base_url
    )
