"""Airflow DAG for document ETL pipeline.

This DAG orchestrates the end-to-end processing of documents:
1. Load raw document and file
2. Clean markdown content
3. Upload assets and replace image links
4. Run image-to-text processing (optional)
5. Split text into chunks
6. Extract keywords (optional)
7. Generate Q&A pairs (optional)
8. Summarize with sliding window (optional)
9. Generate embeddings
10. Index to all enabled storage backends
11. Mark document as processed

Each task is idempotent and handles errors gracefully.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any

from airflow import DAG
from airflow.decorators import task
from airflow.exceptions import AirflowException

from src.deep_parser.config.settings import get_pipeline_config, get_settings
from src.deep_parser.etl.clean import MarkdownCleaner
from src.deep_parser.etl.embed import EmbeddingProcessor
from src.deep_parser.etl.i2t import ImageToTextProcessor
from src.deep_parser.etl.keywords import KeywordExtractor
from src.deep_parser.etl.qa import QAGenerator
from src.deep_parser.etl.split import ChunkSplitter
from src.deep_parser.etl.summary import SlidingWindowSummarizer
from src.deep_parser.indexing.index_manager import IndexManager
from src.deep_parser.logging_config import logger
from src.deep_parser.models import (
    Chunk,
    Document,
    DocumentStatus,
    Embedding,
    Job,
    JobStatus,
    get_async_session,
)
from src.deep_parser.services.image_host import ImageHostService
from src.deep_parser.services.llm_service import get_llm_service
from src.deep_parser.services.storage import StorageService

default_args = {
    "owner": "deep-parser",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    "doc_etl_v1",
    default_args=default_args,
    description="Document ETL pipeline with idempotent processing",
    schedule_interval=None,
    catchup=False,
    max_active_runs=1,
    tags=["etl", "document"],
)


def run_async(coro):
    """Helper to run async functions in synchronous Airflow context."""
    return asyncio.run(coro)


async def get_document_and_job(doc_id: str) -> tuple[Document | None, Job | None]:
    """Get document and job records by doc_id."""
    async with get_async_session() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(Document).where(Document.doc_id == doc_id)
        )
        document = result.scalar_one_or_none()

        job_result = await session.execute(
            select(Job).where(Job.params["doc_id"].astext == str(doc_id))
        )
        job = job_result.scalar_one_or_none()

        return document, job


async def update_document_status(
    doc_id: str,
    status: DocumentStatus,
    error_message: str | None = None,
) -> None:
    """Update document status in database."""
    async with get_async_session() as session:
        from sqlalchemy import select, update

        stmt = (
            update(Document)
            .where(Document.doc_id == doc_id)
            .values(status=status.value, error_message=error_message)
        )
        await session.execute(stmt)
        await session.commit()


async def update_job_status(
    job_id: str,
    status: JobStatus,
    error_message: str | None = None,
) -> None:
    """Update job status in database."""
    async with get_async_session() as session:
        from sqlalchemy import update

        stmt = (
            update(Job)
            .where(Job.job_id == job_id)
            .values(status=status.value, error_message=error_message)
        )
        await session.execute(stmt)
        await session.commit()


async def delete_existing_chunks(doc_id: str) -> None:
    """Delete existing chunks and embeddings for idempotency."""
    async with get_async_session() as session:
        from sqlalchemy import delete

        await session.execute(delete(Embedding).where(Embedding.chunk_id.in_(
            select(Chunk.chunk_id).where(Chunk.doc_id == doc_id)
        )))
        await session.execute(delete(Chunk).where(Chunk.doc_id == doc_id))
        await session.commit()


@task(dag=dag)
def load_raw(**context) -> dict[str, Any]:
    """Load raw document and file from storage.

    Returns:
        Dictionary containing document info and raw markdown content
    """
    doc_id = context["dag_run"].conf["doc_id"]
    logger.info(f"Loading raw document: {doc_id}")

    try:
        async def _load():
            document, job = await get_document_and_job(doc_id)
            if not document:
                raise ValueError(f"Document not found: {doc_id}")

            storage = StorageService()
            markdown_content = storage.read_file(document.raw_storage_path)

            return {
                "doc_id": doc_id,
                "job_id": job.job_id if job else None,
                "raw_markdown": markdown_content,
                "doc_dir": document.raw_storage_path.rsplit("/", 1)[0],
            }

        result = run_async(_load())
        logger.info(f"Successfully loaded document {doc_id}")
        return result

    except Exception as e:
        logger.error(f"Failed to load document {doc_id}: {e}")
        run_async(update_document_status(doc_id, DocumentStatus.FAILED, str(e)))
        raise AirflowException(f"Load failed: {e}")


@task(dag=dag)
def clean_markdown(data: dict[str, Any]) -> dict[str, Any]:
    """Clean markdown content using configured rules.

    Args:
        data: Dictionary containing raw_markdown

    Returns:
        Updated dictionary with cleaned_markdown
    """
    doc_id = data["doc_id"]
    logger.info(f"Cleaning markdown for document: {doc_id}")

    try:
        config = get_pipeline_config()
        cleaner = MarkdownCleaner(config.clean)
        cleaned_text, stats = cleaner.clean(data["raw_markdown"])

        data["cleaned_markdown"] = cleaned_text
        data["clean_stats"] = stats

        logger.info(f"Cleaned markdown for {doc_id}: {stats}")
        return data

    except Exception as e:
        logger.error(f"Failed to clean markdown for {doc_id}: {e}")
        run_async(update_document_status(doc_id, DocumentStatus.FAILED, str(e)))
        raise AirflowException(f"Clean failed: {e}")


@task(dag=dag)
def upload_assets_and_replace_links(data: dict[str, Any]) -> dict[str, Any]:
    """Upload images to image host and replace markdown links.

    Args:
        data: Dictionary containing cleaned_markdown and doc_dir

    Returns:
        Updated dictionary with processed_markdown
    """
    doc_id = data["doc_id"]
    logger.info(f"Uploading assets for document: {doc_id}")

    try:
        settings = get_settings()
        image_host = ImageHostService()
        i2t_processor = ImageToTextProcessor(
            get_pipeline_config().i2t,
            get_llm_service()
        )

        processed_text = i2t_processor.process_markdown(
            data["cleaned_markdown"],
            data["doc_dir"],
            image_host
        )

        data["processed_markdown"] = processed_text
        logger.info(f"Assets uploaded for {doc_id}")
        return data

    except Exception as e:
        logger.error(f"Failed to upload assets for {doc_id}: {e}")
        run_async(update_document_status(doc_id, DocumentStatus.FAILED, str(e)))
        raise AirflowException(f"Asset upload failed: {e}")


@task(dag=dag)
def run_i2t(data: dict[str, Any]) -> dict[str, Any]:
    """Run image-to-text processing if enabled.

    Args:
        data: Dictionary containing processed_markdown

    Returns:
        Same dictionary (i2t already done in upload_assets_and_replace_links)
    """
    doc_id = data["doc_id"]
    config = get_pipeline_config()

    if not config.i2t.enabled:
        logger.info(f"I2T disabled for document: {doc_id}")
        return data

    logger.info(f"I2T already completed in asset upload for: {doc_id}")
    return data


@task(dag=dag)
def split_chunks(data: dict[str, Any]) -> dict[str, Any]:
    """Split markdown into chunks.

    Args:
        data: Dictionary containing processed_markdown

    Returns:
        Updated dictionary with chunks list
    """
    doc_id = data["doc_id"]
    logger.info(f"Splitting chunks for document: {doc_id}")

    try:
        config = get_pipeline_config()
        splitter = ChunkSplitter(config.split)
        chunks = splitter.split(data["processed_markdown"], doc_id)

        data["chunks"] = chunks
        logger.info(f"Split into {len(chunks)} chunks for {doc_id}")
        return data

    except Exception as e:
        logger.error(f"Failed to split chunks for {doc_id}: {e}")
        run_async(update_document_status(doc_id, DocumentStatus.FAILED, str(e)))
        raise AirflowException(f"Split failed: {e}")


@task(dag=dag)
def extract_keywords(data: dict[str, Any]) -> dict[str, Any]:
    """Extract keywords for each chunk if enabled.

    Args:
        data: Dictionary containing chunks list

    Returns:
        Updated dictionary with keywords added to chunks
    """
    doc_id = data["doc_id"]
    config = get_pipeline_config()

    if not config.keywords.enabled:
        logger.info(f"Keyword extraction disabled for document: {doc_id}")
        return data

    logger.info(f"Extracting keywords for document: {doc_id}")

    try:
        llm = get_llm_service()
        extractor = KeywordExtractor(config.keywords, llm)

        for chunk in data["chunks"]:
            keywords = extractor.extract(chunk["content"])
            chunk["keywords"] = keywords

        logger.info(f"Keywords extracted for {doc_id}")
        return data

    except Exception as e:
        logger.error(f"Failed to extract keywords for {doc_id}: {e}")
        run_async(update_document_status(doc_id, DocumentStatus.FAILED, str(e)))
        raise AirflowException(f"Keyword extraction failed: {e}")


@task(dag=dag)
def generate_qas(data: dict[str, Any]) -> dict[str, Any]:
    """Generate Q&A pairs for each chunk if enabled.

    Args:
        data: Dictionary containing chunks list

    Returns:
        Updated dictionary with qas added to chunks
    """
    doc_id = data["doc_id"]
    config = get_pipeline_config()

    if not config.qa.enabled:
        logger.info(f"QA generation disabled for document: {doc_id}")
        return data

    logger.info(f"Generating Q&A for document: {doc_id}")

    try:
        llm = get_llm_service()
        generator = QAGenerator(config.qa, llm)

        for chunk in data["chunks"]:
            qas = generator.generate(chunk["content"])
            chunk["qas"] = qas

        logger.info(f"Q&A generated for {doc_id}")
        return data

    except Exception as e:
        logger.error(f"Failed to generate Q&A for {doc_id}: {e}")
        run_async(update_document_status(doc_id, DocumentStatus.FAILED, str(e)))
        raise AirflowException(f"QA generation failed: {e}")


@task(dag=dag)
def summarize_sliding_window(data: dict[str, Any]) -> dict[str, Any]:
    """Generate sliding window summaries if enabled.

    Args:
        data: Dictionary containing chunks list

    Returns:
        Updated dictionary with summary chunks added
    """
    doc_id = data["doc_id"]
    config = get_pipeline_config()

    if not config.summary.enabled:
        logger.info(f"Summarization disabled for document: {doc_id}")
        return data

    logger.info(f"Summarizing with sliding window for document: {doc_id}")

    try:
        llm = get_llm_service()
        summarizer = SlidingWindowSummarizer(config.summary, llm)
        summary_chunks = summarizer.summarize(data["chunks"])

        data["chunks"].extend(summary_chunks)
        logger.info(f"Generated {len(summary_chunks)} summary chunks for {doc_id}")
        return data

    except Exception as e:
        logger.error(f"Failed to summarize for {doc_id}: {e}")
        run_async(update_document_status(doc_id, DocumentStatus.FAILED, str(e)))
        raise AirflowException(f"Summarization failed: {e}")


@task(dag=dag)
def embed_chunks(data: dict[str, Any]) -> dict[str, Any]:
    """Generate embeddings for all chunks.

    Args:
        data: Dictionary containing chunks list

    Returns:
        Updated dictionary with embeddings added to chunks
    """
    doc_id = data["doc_id"]
    logger.info(f"Generating embeddings for document: {doc_id}")

    try:
        config = get_pipeline_config()
        llm = get_llm_service()
        processor = EmbeddingProcessor(config.embed, llm)

        chunks_with_embeddings = processor.embed_chunks(data["chunks"])
        data["chunks"] = chunks_with_embeddings

        logger.info(f"Embeddings generated for {len(chunks_with_embeddings)} chunks in {doc_id}")
        return data

    except Exception as e:
        logger.error(f"Failed to generate embeddings for {doc_id}: {e}")
        run_async(update_document_status(doc_id, DocumentStatus.FAILED, str(e)))
        raise AirflowException(f"Embedding failed: {e}")


@task(dag=dag)
def index_to_stores(data: dict[str, Any]) -> dict[str, Any]:
    """Index chunks to all enabled storage backends.

    Args:
        data: Dictionary containing chunks with embeddings

    Returns:
        Same dictionary
    """
    doc_id = data["doc_id"]
    logger.info(f"Indexing to storage backends for document: {doc_id}")

    try:
        async def _index():
            await delete_existing_chunks(doc_id)

            config = get_pipeline_config()
            settings = get_settings()
            index_manager = IndexManager(config.index, settings)
            await index_manager.index_chunks(data["chunks"], doc_id)

        run_async(_index())
        logger.info(f"Successfully indexed {len(data['chunks'])} chunks for {doc_id}")
        return data

    except Exception as e:
        logger.error(f"Failed to index for {doc_id}: {e}")
        run_async(update_document_status(doc_id, DocumentStatus.FAILED, str(e)))
        raise AirflowException(f"Indexing failed: {e}")


@task(dag=dag)
def mark_done(data: dict[str, Any]) -> None:
    """Mark document and job as successfully processed.

    Args:
        data: Dictionary containing doc_id and job_id
    """
    doc_id = data["doc_id"]
    job_id = data.get("job_id")
    logger.info(f"Marking {doc_id} as done")

    try:
        run_async(update_document_status(doc_id, DocumentStatus.INDEXED))

        if job_id:
            run_async(update_job_status(job_id, JobStatus.SUCCESS))

        logger.info(f"Document {doc_id} successfully processed")

    except Exception as e:
        logger.error(f"Failed to mark {doc_id} as done: {e}")
        raise AirflowException(f"Mark done failed: {e}")


# Define task dependencies
(
    load_raw()
    >> clean_markdown()
    >> upload_assets_and_replace_links()
    >> run_i2t()
    >> split_chunks()
    >> extract_keywords()
    >> generate_qas()
    >> summarize_sliding_window()
    >> embed_chunks()
    >> index_to_stores()
    >> mark_done()
)
