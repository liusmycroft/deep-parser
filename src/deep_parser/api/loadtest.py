from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.deep_parser.config.settings import get_settings
from src.deep_parser.loadtest.load_tester import LoadTester
from src.deep_parser.logging_config import logger
from src.deep_parser.models.database import get_async_session
from src.deep_parser.models.job import Job, JobStatus, JobType

router = APIRouter(prefix="/loadtest", tags=["loadtest"])


@router.post("/")
async def run_load_test(
    queries: list[str],
    concurrency: int = 10,
    duration_seconds: int = 60,
    retrieval_params: dict | None = None,
    backend: str = "milvus",
    session: AsyncSession = Depends(get_async_session)
):
    """Execute load test on retrieval API.
    
    Creates a job record, runs concurrent load testing, and returns performance metrics.
    
    Args:
        queries: List of query strings to test
        concurrency: Number of concurrent requests
        duration_seconds: Test duration in seconds
        retrieval_params: Optional retrieval parameters
        backend: Vector backend to use (milvus, es, clickhouse)
        session: Database session
        
    Returns:
        Load test results with performance metrics
    """
    if not queries:
        raise HTTPException(
            status_code=400,
            detail="Queries list cannot be empty"
        )

    retrieval_params = retrieval_params or {}
    
    job = Job(
        job_type=JobType.LOAD_TEST.value,
        params={
            "queries": queries,
            "concurrency": concurrency,
            "duration_seconds": duration_seconds,
            "retrieval_params": retrieval_params,
            "backend": backend
        },
        status=JobStatus.QUEUED.value
    )
    
    session.add(job)
    await session.commit()
    await session.refresh(job)
    
    logger.info(f"Created load test job: {job.job_id}")
    
    job.status = JobStatus.RUNNING.value
    await session.commit()
    
    try:
        settings = get_settings()
        base_url = f"http://{settings.server_host}:{settings.server_port}"
        
        if retrieval_params and "routes" in retrieval_params:
            if "vector" in retrieval_params["routes"]:
                retrieval_params["routes"]["vector"]["backend"] = backend
        else:
            retrieval_params["routes"] = {
                "es_text": True,
                "vector": {"enabled": True, "backend": backend}
            }
        
        tester = LoadTester(base_url)
        result = await tester.run_builtin_test(
            queries=queries,
            concurrency=concurrency,
            duration_seconds=duration_seconds,
            retrieval_params=retrieval_params
        )
        
        job.status = JobStatus.SUCCESS.value
        await session.commit()
        
        logger.info(f"Load test job completed: {job.job_id}")
        
        return {
            "job_id": job.job_id,
            "status": job.status,
            "result": result
        }
        
    except Exception as e:
        job.status = JobStatus.FAILED.value
        job.error_message = str(e)
        await session.commit()
        
        logger.error(f"Load test job failed: {job.job_id}, error: {e}")
        
        raise HTTPException(
            status_code=500,
            detail=f"Load test failed: {str(e)}"
        )
