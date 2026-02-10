"""File storage service for managing document files."""

import mimetypes
import zipfile
from pathlib import Path
from typing import Tuple

from deep_parser.config.settings import get_settings
from deep_parser.logging_config import logger


class StorageService:
    """Service for managing file storage operations."""

    def __init__(self, base_path: str):
        """Initialize storage service with base path.

        Args:
            base_path: Root directory for file storage
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"StorageService initialized with base_path: {self.base_path}")

    def get_document_dir(self, doc_id: str) -> Path:
        """Get the directory path for a document.

        Args:
            doc_id: Document ID

        Returns:
            Path to document directory
        """
        doc_dir = self.base_path / "documents" / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        return doc_dir

    def save_uploaded_file(self, doc_id: str, filename: str, content: bytes) -> Path:
        """Save uploaded file to document directory.

        Args:
            doc_id: Document ID
            filename: Name of the file
            content: File content as bytes

        Returns:
            Path to saved file
        """
        doc_dir = self.get_document_dir(doc_id)
        file_path = doc_dir / filename
        file_path.write_bytes(content)
        logger.info(f"Saved uploaded file: {file_path}")
        return file_path

    def extract_zip(self, doc_id: str, zip_path: Path) -> Tuple[Path, list[str]]:
        """Extract zip file and validate structure.

        Args:
            doc_id: Document ID
            zip_path: Path to zip file

        Returns:
            Tuple of (markdown file path, list of asset relative paths)

        Raises:
            ValueError: If zip does not contain exactly one markdown file
        """
        doc_dir = self.get_document_dir(doc_id)
        extract_dir = doc_dir / "extracted"
        extract_dir.mkdir(exist_ok=True)

        md_files = []
        asset_files = []

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

            for file_info in zip_ref.infolist():
                if file_info.is_dir():
                    continue

                file_path = extract_dir / file_info.filename
                relative_path = file_info.filename

                if file_path.suffix.lower() == '.md':
                    md_files.append(file_path)
                else:
                    asset_files.append(relative_path)

        if len(md_files) != 1:
            raise ValueError(
                f"Zip must contain exactly one markdown file, found {len(md_files)}"
            )

        md_path = md_files[0]
        logger.info(
            f"Extracted zip: {zip_path} -> md: {md_path}, assets: {len(asset_files)}"
        )
        return md_path, asset_files

    def read_file(self, file_path: Path) -> str:
        """Read text file content.

        Args:
            file_path: Path to file

        Returns:
            File content as string
        """
        return file_path.read_text(encoding='utf-8')


def get_storage_service() -> StorageService:
    """Factory function to get storage service instance.

    Returns:
        StorageService instance configured from settings
    """
    settings = get_settings()
    return StorageService(base_path=settings.storage_base_path)
