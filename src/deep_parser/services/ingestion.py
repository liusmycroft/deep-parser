"""Ingestion service for processing uploaded documents."""

import mimetypes
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from deep_parser.logging_config import logger
from deep_parser.models.asset import Asset
from deep_parser.models.document import Document, DocumentStatus, SourceType
from deep_parser.models.job import Job, JobStatus, JobType
from deep_parser.services.image_host import ImageHostService
from deep_parser.services.storage import StorageService


class IngestionService:
    """Service for ingesting uploaded documents."""

    def __init__(
        self,
        session: AsyncSession,
        storage: StorageService,
        image_host: ImageHostService
    ):
        """Initialize ingestion service.

        Args:
            session: Async database session
            storage: Storage service instance
            image_host: Image host service instance
        """
        self.session = session
        self.storage = storage
        self.image_host = image_host

    async def ingest_zip(
        self,
        file_content: bytes,
        filename: str,
        source_type: str = "manual"
    ) -> Dict[str, Any]:
        """Ingest a zip file containing markdown and assets.

        Args:
            file_content: Zip file content
            filename: Name of the zip file
            source_type: Source type (wechat, zhihu, manual)

        Returns:
            Dictionary with doc_id, title, assets_count, md_path

        Raises:
            ValueError: If zip structure is invalid
        """
        doc_id = str(uuid4())

        logger.info(
            f"Ingesting zip for doc {doc_id}: {filename}, "
            f"source_type: {source_type}"
        )

        zip_path = self.storage.save_uploaded_file(doc_id, filename, file_content)

        try:
            md_path, asset_files = self.storage.extract_zip(doc_id, zip_path)
        except ValueError as e:
            logger.error(f"Failed to extract zip for doc {doc_id}: {e}")
            raise

        title = md_path.stem

        document = Document(
            doc_id=doc_id,
            source_type=source_type,
            title=title,
            raw_storage_path=str(zip_path),
            cleaned_markdown_path=str(md_path),
            status=DocumentStatus.UPLOADED.value
        )
        self.session.add(document)

        assets_count = 0
        for asset_file in asset_files:
            asset_path = self.storage.get_document_dir(doc_id) / "extracted" / asset_file

            if not asset_path.exists():
                logger.warning(f"Asset file not found: {asset_path}")
                continue

            asset_size = asset_path.stat().st_size
            mime_type, _ = mimetypes.guess_type(asset_file)
            if mime_type is None:
                mime_type = "application/octet-stream"

            image_host_url: str | None = None
            if mime_type.startswith("image/"):
                try:
                    image_host_url = self.image_host.upload_image(doc_id, asset_path)
                except Exception as e:
                    logger.error(f"Failed to upload image for doc {doc_id}: {e}")

            asset = Asset(
                doc_id=doc_id,
                orig_path=asset_file,
                mime_type=mime_type,
                size=asset_size,
                image_host_url=image_host_url
            )
            self.session.add(asset)
            assets_count += 1

        job = Job(
            job_id=str(uuid4()),
            job_type=JobType.INGEST.value,
            params={
                "doc_id": doc_id,
                "filename": filename,
                "assets_count": assets_count
            },
            status=JobStatus.SUCCESS.value
        )
        self.session.add(job)

        await self.session.commit()

        logger.info(
            f"Successfully ingested zip for doc {doc_id}: "
            f"{assets_count} assets created"
        )

        return {
            "doc_id": doc_id,
            "title": title,
            "assets_count": assets_count,
            "md_path": str(md_path)
        }

    async def ingest_markdown(
        self,
        file_content: bytes,
        filename: str,
        source_type: str = "manual"
    ) -> Dict[str, Any]:
        """Ingest a single markdown file.

        Args:
            file_content: Markdown file content
            filename: Name of the markdown file
            source_type: Source type (wechat, zhihu, manual)

        Returns:
            Dictionary with doc_id, title, md_path
        """
        doc_id = str(uuid4())

        logger.info(
            f"Ingesting markdown for doc {doc_id}: {filename}, "
            f"source_type: {source_type}"
        )

        file_path = self.storage.save_uploaded_file(doc_id, filename, file_content)

        title = Path(filename).stem

        document = Document(
            doc_id=doc_id,
            source_type=source_type,
            title=title,
            raw_storage_path=str(file_path),
            cleaned_markdown_path=str(file_path),
            status=DocumentStatus.UPLOADED.value
        )
        self.session.add(document)

        job = Job(
            job_id=str(uuid4()),
            job_type=JobType.INGEST.value,
            params={
                "doc_id": doc_id,
                "filename": filename
            },
            status=JobStatus.SUCCESS.value
        )
        self.session.add(job)

        await self.session.commit()

        logger.info(f"Successfully ingested markdown for doc {doc_id}")

        return {
            "doc_id": doc_id,
            "title": title,
            "md_path": str(file_path)
        }

    async def ingest_multiple_markdowns(
        self,
        files: list[tuple[bytes, str]],
        source_type: str = "manual"
    ) -> list[Dict[str, Any]]:
        """Ingest multiple markdown files.

        Args:
            files: List of (file_content, filename) tuples
            source_type: Source type (wechat, zhihu, manual)

        Returns:
            List of ingestion result dictionaries
        """
        results = []

        logger.info(f"Ingesting {len(files)} markdown files")

        for file_content, filename in files:
            try:
                result = await self.ingest_markdown(
                    file_content,
                    filename,
                    source_type
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to ingest markdown {filename}: {e}")
                results.append({
                    "error": str(e),
                    "filename": filename
                })

        logger.info(
            f"Finished ingesting {len(files)} markdown files, "
            f"{len(results)} succeeded"
        )

        return results
