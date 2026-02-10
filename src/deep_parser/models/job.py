"""Job model for tracking background processing jobs."""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class JobType(str, Enum):
    """Enumeration of job types."""
    INGEST = "ingest"
    ETL = "etl"
    RETRIEVAL_EVAL = "retrieval_eval"
    LOAD_TEST = "load_test"


class JobStatus(str, Enum):
    """Enumeration of job statuses."""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class Job(Base):
    """
    Job model for tracking background processing jobs.
    
    Attributes:
        job_id: Primary key UUID
        job_type: Type of job to execute
        params: Job parameters as JSON
        status: Current job status
        airflow_dag_run_id: Airflow DAG run identifier
        created_at: Creation timestamp
        updated_at: Last update timestamp
        error_message: Error message if job failed
    """
    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4())
    )
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    params: Mapped[dict] = mapped_column(MySQLJSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=JobStatus.QUEUED.value
    )
    airflow_dag_run_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
