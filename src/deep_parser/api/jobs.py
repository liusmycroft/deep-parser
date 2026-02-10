from fastapi import Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.deep_parser.logging_config import logger
from src.deep_parser.models.database import get_async_session
from src.deep_parser.models.job import Job, JobStatus

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/")
async def list_jobs(
    status: str | None = None,
    job_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session)
):
    """List all jobs with optional filtering and pagination.
    
    Args:
        status: Filter by job status
        job_type: Filter by job type
        page: Page number (1-indexed)
        page_size: Number of items per page
        session: Database session
        
    Returns:
        Paginated list of jobs
    """
    query = select(Job)
    
    if status:
        query = query.where(Job.status == status)
    
    if job_type:
        query = query.where(Job.job_type == job_type)
    
    query = query.order_by(Job.created_at.desc())
    
    total_result = await session.execute(select(Job))
    total = len(total_result.scalars().all())
    
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await session.execute(query)
    jobs = result.scalars().all()
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "jobs": [
            {
                "job_id": job.job_id,
                "job_type": job.job_type,
                "status": job.status,
                "params": job.params,
                "error_message": job.error_message,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None
            }
            for job in jobs
        ]
    }


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    session: AsyncSession = Depends(get_async_session)
):
    """Get details of a specific job.
    
    Args:
        job_id: Job identifier
        session: Database session
        
    Returns:
        Job details
    """
    result = await session.execute(select(Job).where(Job.job_id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job not found: {job_id}"
        )
    
    return {
        "job_id": job.job_id,
        "job_type": job.job_type,
        "status": job.status,
        "params": job.params,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "airflow_dag_run_id": job.airflow_dag_run_id
    }


@router.post("/{job_id}/retry")
async def retry_job(
    job_id: str,
    session: AsyncSession = Depends(get_async_session)
):
    """Retry a failed job.
    
    Args:
        job_id: Job identifier
        session: Database session
        
    Returns:
        Updated job information
    """
    result = await session.execute(select(Job).where(Job.job_id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job not found: {job_id}"
        )
    
    if job.status != JobStatus.FAILED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Can only retry failed jobs, current status: {job.status}"
        )
    
    job.status = JobStatus.QUEUED.value
    job.error_message = None
    await session.commit()
    
    logger.info(f"Job queued for retry: {job_id}")
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "message": "Job queued for retry"
    }
