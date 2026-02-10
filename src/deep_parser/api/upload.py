from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from deep_parser.models.database import get_async_session
from deep_parser.services.image_host import get_image_host_service
from deep_parser.services.ingestion import IngestionService
from deep_parser.services.storage import get_storage_service

router = APIRouter(prefix="/upload", tags=["upload"])


async def get_ingestion_service(
    session: AsyncSession = Depends(get_async_session)
) -> IngestionService:
    """Dependency injection for IngestionService.

    Args:
        session: Async database session

    Returns:
        IngestionService instance
    """
    storage = get_storage_service()
    image_host = get_image_host_service()
    return IngestionService(session=session, storage=storage, image_host=image_host)


@router.post("/zip")
async def upload_zip(
    file: UploadFile = File(...),
    source_type: str = "manual",
    ingestion_service: IngestionService = Depends(get_ingestion_service)
):
    """Upload a zip file containing markdown and assets.

    Args:
        file: Uploaded zip file
        source_type: Source type (wechat, zhihu, manual)
        ingestion_service: Ingestion service instance

    Returns:
        Upload result with document information

    Raises:
        ValueError: If zip structure is invalid
    """
    file_content = await file.read()
    result = await ingestion_service.ingest_zip(
        file_content=file_content,
        filename=file.filename or "upload.zip",
        source_type=source_type
    )
    return {"status": "success", "data": result}


@router.post("/markdown")
async def upload_markdown(
    files: list[UploadFile] = File(...),
    source_type: str = "manual",
    ingestion_service: IngestionService = Depends(get_ingestion_service)
):
    """Upload multiple markdown files.

    Args:
        files: List of uploaded markdown files
        source_type: Source type (wechat, zhihu, manual)
        ingestion_service: Ingestion service instance

    Returns:
        Upload results for all files
    """
    file_tuples = []
    for file in files:
        content = await file.read()
        file_tuples.append((content, file.filename or "upload.md"))

    results = await ingestion_service.ingest_multiple_markdowns(
        files=file_tuples,
        source_type=source_type
    )
    return {"status": "success", "data": results}