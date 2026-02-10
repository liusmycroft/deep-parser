from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.deep_parser.config.settings import get_settings, get_pipeline_config, PipelineConfigs
from src.deep_parser.logging_config import logger
from src.deep_parser.models.database import get_async_session

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/")
async def get_current_config():
    """Get current active configuration.
    
    Returns:
        Current application settings and pipeline configuration
    """
    settings = get_settings()
    pipeline_config = get_pipeline_config()
    
    return {
        "settings": settings.model_dump(exclude={"openai_api_key", "es_password", "clickhouse_password"}),
        "pipeline": pipeline_config.model_dump()
    }


@router.put("/")
async def update_config(
    config_update: dict,
    session: AsyncSession = Depends(get_async_session)
):
    """Update configuration and save new version.
    
    Args:
        config_update: Configuration updates
        session: Database session
        
    Returns:
        Updated configuration
    """
    logger.info(f"Configuration update requested")
    
    return {
        "message": "Configuration update not yet implemented",
        "note": "This endpoint requires configuration versioning model"
    }


@router.get("/versions")
async def list_config_versions(
    session: AsyncSession = Depends(get_async_session)
):
    """List all configuration versions.
    
    Args:
        session: Database session
        
    Returns:
        List of configuration versions
    """
    logger.info(f"Configuration versions requested")
    
    return {
        "message": "Configuration versioning not yet implemented",
        "note": "This endpoint requires configuration versioning model",
        "versions": []
    }


@router.post("/versions/{version_id}/activate")
async def activate_config_version(
    version_id: str,
    session: AsyncSession = Depends(get_async_session)
):
    """Activate a specific configuration version.
    
    Args:
        version_id: Configuration version identifier
        session: Database session
        
    Returns:
        Activation status
    """
    logger.info(f"Configuration version activation requested: {version_id}")
    
    return {
        "message": "Configuration versioning not yet implemented",
        "note": "This endpoint requires configuration versioning model",
        "version_id": version_id
    }
