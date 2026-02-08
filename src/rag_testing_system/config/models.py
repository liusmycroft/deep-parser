"""Configuration models using Pydantic for type-safe configuration."""

from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class LogLevel(str, Enum):
    """Supported log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ElasticsearchConfig(BaseModel):
    """Elasticsearch database configuration."""
    hosts: List[str] = Field(
        default=["http://localhost:9200"],
        description="List of Elasticsearch host URLs"
    )
    index_name: str = Field(
        default="rag_chunks",
        description="Name of the Elasticsearch index"
    )
    shards: int = Field(
        default=1,
        ge=1,
        description="Number of primary shards"
    )
    replicas: int = Field(
        default=1,
        ge=0,
        description="Number of replica shards"
    )
    refresh_interval: str = Field(
        default="1s",
        description="Index refresh interval"
    )
    username: Optional[str] = Field(
        default=None,
        description="Elasticsearch username for authentication"
    )
    password: Optional[str] = Field(
        default=None,
        description="Elasticsearch password for authentication"
    )


class MilvusConfig(BaseModel):
    """Milvus vector database configuration."""
    host: str = Field(
        default="localhost",
        description="Milvus server host"
    )
    port: int = Field(
        default=19530,
        ge=1,
        le=65535,
        description="Milvus server port"
    )
    collection_name: str = Field(
        default="rag_chunks",
        description="Name of the Milvus collection"
    )
    index_type: str = Field(
        default="HNSW",
        description="Index type (HNSW, IVF_FLAT, IVF_SQ8)"
    )
    metric_type: str = Field(
        default="COSINE",
        description="Distance metric (COSINE, L2, IP)"
    )
    nlist: int = Field(
        default=1024,
        ge=1,
        description="Number of cluster units for IVF indexes"
    )
    username: Optional[str] = Field(
        default=None,
        description="Milvus username for authentication"
    )
    password: Optional[str] = Field(
        default=None,
        description="Milvus password for authentication"
    )


class ClickHouseConfig(BaseModel):
    """ClickHouse database configuration."""
    host: str = Field(
        default="localhost",
        description="ClickHouse server host"
    )
    port: int = Field(
        default=9000,
        ge=1,
        le=65535,
        description="ClickHouse server port"
    )
    database: str = Field(
        default="rag_system",
        description="ClickHouse database name"
    )
    table_name: str = Field(
        default="rag_chunks",
        description="Name of the ClickHouse table"
    )
    engine: str = Field(
        default="MergeTree",
        description="Table engine type"
    )
    partition_key: Optional[str] = Field(
        default=None,
        description="Partition key for the table"
    )
    username: Optional[str] = Field(
        default="default",
        description="ClickHouse username"
    )
    password: Optional[str] = Field(
        default="",
        description="ClickHouse password"
    )


class HBaseConfig(BaseModel):
    """HBase database configuration."""
    host: str = Field(
        default="localhost",
        description="HBase Thrift server host"
    )
    port: int = Field(
        default=9090,
        ge=1,
        le=65535,
        description="HBase Thrift server port"
    )
    table_name: str = Field(
        default="rag_documents",
        description="Name of the HBase table"
    )
    column_family: str = Field(
        default="cf",
        description="Column family name"
    )


class DatabaseConfig(BaseModel):
    """Combined database configuration."""
    elasticsearch: ElasticsearchConfig = Field(
        default_factory=ElasticsearchConfig,
        description="Elasticsearch configuration"
    )
    clickhouse: ClickHouseConfig = Field(
        default_factory=ClickHouseConfig,
        description="ClickHouse configuration"
    )
    milvus: MilvusConfig = Field(
        default_factory=MilvusConfig,
        description="Milvus configuration"
    )
    hbase: HBaseConfig = Field(
        default_factory=HBaseConfig,
        description="HBase configuration"
    )


class EmbeddingConfig(BaseModel):
    """Embedding model configuration."""
    model_name: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Name of the embedding model"
    )
    model_type: str = Field(
        default="sentence-transformers",
        description="Type of embedding model (sentence-transformers, openai)"
    )
    api_endpoint: Optional[str] = Field(
        default=None,
        description="API endpoint for external embedding services"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API key for external embedding services"
    )
    batch_size: int = Field(
        default=32,
        ge=1,
        description="Batch size for embedding generation"
    )
    embedding_dim: int = Field(
        default=384,
        ge=1,
        description="Dimensionality of embedding vectors"
    )


class ProcessingConfig(BaseModel):
    """Document processing configuration."""
    chunk_size: int = Field(
        default=512,
        ge=1,
        description="Maximum size of text chunks in characters"
    )
    chunk_overlap: int = Field(
        default=50,
        ge=0,
        description="Overlap between consecutive chunks in characters"
    )
    chunk_separator: str = Field(
        default="\n\n",
        description="Separator for splitting text into chunks"
    )
    max_document_size: int = Field(
        default=5000,
        ge=1,
        description="Maximum document size before logging warning"
    )
    image_to_text_api_url: Optional[str] = Field(
        default=None,
        description="URL for image-to-text conversion service"
    )
    image_to_text_api_key: Optional[str] = Field(
        default=None,
        description="API key for image-to-text service"
    )
    image_placeholder_text: str = Field(
        default="[Image description unavailable]",
        description="Placeholder text when image conversion fails"
    )
    header_patterns: List[str] = Field(
        default=[
            r"^Date:.*$",
            r"^Author:.*$",
            r"^Navigation:.*$",
            r"^\[.*\]\(.*\)$",  # Navigation links
        ],
        description="Regex patterns for header content to remove"
    )
    footer_patterns: List[str] = Field(
        default=[
            r"^Copyright.*$",
            r"^©.*$",
            r"^Advertisement.*$",
            r"^Related links:.*$",
        ],
        description="Regex patterns for footer content to remove"
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level"
    )
    format: str = Field(
        default="json",
        description="Log format (json or text)"
    )
    output_file: Optional[str] = Field(
        default=None,
        description="Path to log file (None for stdout only)"
    )
    enable_console: bool = Field(
        default=True,
        description="Enable console logging"
    )


class RetrievalConfig(BaseModel):
    """Retrieval configuration."""
    default_top_k: int = Field(
        default=10,
        ge=1,
        description="Default number of results to return"
    )
    default_score_threshold: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Default minimum relevance score threshold"
    )
    elasticsearch_hybrid_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight for combining BM25 and vector scores in Elasticsearch"
    )


class PerformanceConfig(BaseModel):
    """Performance testing configuration."""
    default_qps: int = Field(
        default=10,
        ge=1,
        description="Default queries per second for load tests"
    )
    default_duration: int = Field(
        default=60,
        ge=1,
        description="Default test duration in seconds"
    )
    default_concurrency: int = Field(
        default=10,
        ge=1,
        description="Default number of concurrent workers"
    )
    warmup_duration: int = Field(
        default=5,
        ge=0,
        description="Warmup period in seconds before measurement"
    )


class WorkflowConfig(BaseModel):
    """Airflow workflow configuration."""
    dag_id: str = Field(
        default="rag_etl_pipeline",
        description="Airflow DAG identifier"
    )
    schedule_interval: Optional[str] = Field(
        default=None,
        description="Cron expression for DAG scheduling"
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum number of task retries"
    )
    retry_delay: int = Field(
        default=300,
        ge=0,
        description="Delay between retries in seconds"
    )
    email_on_failure: bool = Field(
        default=False,
        description="Send email notifications on task failure"
    )
    email_recipients: List[str] = Field(
        default=[],
        description="Email addresses for failure notifications"
    )


class WebConfig(BaseModel):
    """Web API configuration."""
    host: str = Field(
        default="0.0.0.0",
        description="API server host"
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="API server port"
    )
    enable_cors: bool = Field(
        default=True,
        description="Enable CORS"
    )
    cors_origins: List[str] = Field(
        default=["*"],
        description="Allowed CORS origins"
    )
    enable_auth: bool = Field(
        default=False,
        description="Enable JWT authentication"
    )
    jwt_secret: Optional[str] = Field(
        default=None,
        description="Secret key for JWT token generation"
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm"
    )


class RAGSystemConfig(BaseModel):
    """Main configuration for the RAG Testing System."""
    database: DatabaseConfig = Field(
        default_factory=DatabaseConfig,
        description="Database configurations"
    )
    embedding: EmbeddingConfig = Field(
        default_factory=EmbeddingConfig,
        description="Embedding model configuration"
    )
    processing: ProcessingConfig = Field(
        default_factory=ProcessingConfig,
        description="Document processing configuration"
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Logging configuration"
    )
    retrieval: RetrievalConfig = Field(
        default_factory=RetrievalConfig,
        description="Retrieval configuration"
    )
    performance: PerformanceConfig = Field(
        default_factory=PerformanceConfig,
        description="Performance testing configuration"
    )
    workflow: WorkflowConfig = Field(
        default_factory=WorkflowConfig,
        description="Workflow orchestration configuration"
    )
    web: WebConfig = Field(
        default_factory=WebConfig,
        description="Web API configuration"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "database": {
                    "elasticsearch": {
                        "hosts": ["http://elasticsearch:9200"],
                        "index_name": "rag_chunks"
                    }
                },
                "embedding": {
                    "model_name": "sentence-transformers/all-MiniLM-L6-v2"
                },
                "processing": {
                    "chunk_size": 512,
                    "chunk_overlap": 50
                }
            }
        }
    }
