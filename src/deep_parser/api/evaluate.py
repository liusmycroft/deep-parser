from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.deep_parser.config.settings import get_settings
from src.deep_parser.evaluation.ragas_eval import RagasEvaluator
from src.deep_parser.logging_config import logger
from src.deep_parser.models.database import get_async_session
from src.deep_parser.models.job import Job, JobStatus, JobType
from src.deep_parser.retrieval.retriever import RetrieverService
from src.deep_parser.services.llm_service import get_llm_service

router = APIRouter(prefix="/evaluate", tags=["evaluate"])


async def get_retriever_service() -> RetrieverService:
    """Dependency injection for RetrieverService.
    
    Returns:
        Configured RetrieverService instance
    """
    settings = get_settings()
    llm_service = get_llm_service()
    return RetrieverService(settings, llm_service)


@router.post("/")
async def evaluate(
    dataset_path: str,
    retrieval_params: dict | None = None,
    session: AsyncSession = Depends(get_async_session),
    retriever_service: RetrieverService = Depends(get_retriever_service)
):
    """Execute retrieval evaluation on a dataset.
    
    Creates a job record, runs evaluation using the specified dataset,
    and returns evaluation metrics.
    
    Args:
        dataset_path: Path to JSONL dataset file
        retrieval_params: Optional retrieval parameters
        session: Database session
        retriever_service: Retrieval service instance
        
    Returns:
        Evaluation results with metrics and failed cases
    """
    retrieval_params = retrieval_params or {}
    
    job = Job(
        job_type=JobType.RETRIEVAL_EVAL.value,
        params={
            "dataset_path": dataset_path,
            "retrieval_params": retrieval_params
        },
        status=JobStatus.QUEUED.value
    )
    
    session.add(job)
    await session.commit()
    await session.refresh(job)
    
    logger.info(f"Created evaluation job: {job.job_id}")
    
    job.status = JobStatus.RUNNING.value
    await session.commit()
    
    try:
        evaluator = RagasEvaluator(retriever_service)
        result = await evaluator.evaluate(dataset_path, retrieval_params)
        
        job.status = JobStatus.SUCCESS.value
        await session.commit()
        
        logger.info(f"Evaluation job completed: {job.job_id}")
        
        return {
            "job_id": job.job_id,
            "status": job.status,
            "result": result
        }
        
    except Exception as e:
        job.status = JobStatus.FAILED.value
        job.error_message = str(e)
        await session.commit()
        
        logger.error(f"Evaluation job failed: {job.job_id}, error: {e}")
        
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {str(e)}"
        )