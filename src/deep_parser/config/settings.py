"""Configuration management for Deep Parser.

This module provides:
- Settings class for environment variable configuration using pydantic-settings
- Pydantic models for YAML-based pipeline configurations
- Loader functions for YAML configurations
- Singleton pattern for settings access
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CleanConfig(BaseModel):
    """Configuration for text cleaning pipeline stage.

    Attributes:
        remove_regex: List of regex patterns to remove from text
        remove_contains: List of substrings that trigger removal
        min_length_after_clean: Minimum text length after cleaning
    """

    remove_regex: List[str] = Field(default_factory=list)
    remove_contains: List[str] = Field(default_factory=list)
    min_length_after_clean: int = 200


class I2tConfig(BaseModel):
    """Configuration for image-to-text pipeline stage.

    Attributes:
        enabled: Whether image-to-text processing is enabled
        provider: LLM provider for image-to-text (e.g., openai)
        timeout_sec: Request timeout in seconds
        max_retries: Maximum retry attempts
        fallback_on_error: Fallback strategy on error (skip/raise)
    """

    enabled: bool = True
    provider: str = "openai"
    timeout_sec: int = 30
    max_retries: int = 3
    fallback_on_error: str = "skip"


class SplitConfig(BaseModel):
    """Configuration for text splitting pipeline stage.

    Attributes:
        separators: List of separators for splitting text
        min_tokens: Minimum tokens per chunk
        max_tokens: Maximum tokens per chunk
        merge_strategy: Strategy for merging chunks (prefer_prev/next)
        tokenizer: Tokenizer name (e.g., cl100k_base)
    """

    separators: List[str] = Field(default_factory=lambda: ["\n## ", "\n### ", "\n\n", "\n"])
    min_tokens: int = 200
    max_tokens: int = 800
    merge_strategy: str = "prefer_prev"
    tokenizer: str = "cl100k_base"


class KeywordsConfig(BaseModel):
    """Configuration for keyword extraction pipeline stage.

    Attributes:
        enabled: Whether keyword extraction is enabled
        top_n: Number of keywords to extract
        llm_provider: LLM provider for extraction
        prompt_template: Prompt template for extraction
        timeout_sec: Request timeout in seconds
        max_retries: Maximum retry attempts
    """

    enabled: bool = True
    top_n: int = 8
    llm_provider: str = "openai"
    prompt_template: str = (
        'Extract the top {top_n} keywords from the following text.\n'
        'Return a JSON array of strings, e.g. ["keyword1", "keyword2"].\n'
        'Text:\n{text}'
    )
    timeout_sec: int = 30
    max_retries: int = 2


class QaConfig(BaseModel):
    """Configuration for question-answer generation pipeline stage.

    Attributes:
        enabled: Whether QA generation is enabled
        top_n: Number of QA pairs to generate
        llm_provider: LLM provider for generation
        prompt_template: Prompt template for generation
        timeout_sec: Request timeout in seconds
        max_retries: Maximum retry attempts
    """

    enabled: bool = True
    top_n: int = 3
    llm_provider: str = "openai"
    prompt_template: str = (
        'Based on the following text, generate {top_n} question-answer pairs.\n'
        'Return a JSON array of objects with "q" and "a" fields.\n'
        'Example: [{"q": "What is X?", "a": "X is ..."}]\n'
        'Text:\n{text}'
    )
    timeout_sec: int = 30
    max_retries: int = 2


class SummaryConfig(BaseModel):
    """Configuration for summarization pipeline stage.

    Attributes:
        enabled: Whether summarization is enabled
        window_size: Context window size for hierarchical summarization
        layers: Number of hierarchical layers
        max_tokens_summary: Maximum tokens in summary
        llm_provider: LLM provider for summarization
        prompt_template: Prompt template for summarization
    """

    enabled: bool = False
    window_size: int = 2
    layers: int = 3
    max_tokens_summary: int = 500
    llm_provider: str = "openai"
    prompt_template: str = (
        'Summarize the following text segments into a concise summary.\n'
        'Keep the summary under {max_tokens} tokens.\n'
        'Text segments:\n{text}'
    )


class EmbedConfig(BaseModel):
    """Configuration for embedding generation pipeline stage.

    Attributes:
        provider: Embedding provider (e.g., openai)
        model: Embedding model name
        dim: Embedding dimension
        batch_size: Batch size for embedding generation
        timeout_sec: Request timeout in seconds
        max_retries: Maximum retry attempts
    """

    provider: str = "openai"
    model: str = "text-embedding-3-small"
    dim: int = 1536
    batch_size: int = 32
    timeout_sec: int = 60
    max_retries: int = 3


class IndexConfig(BaseModel):
    """Configuration for indexing pipeline stage.

    Attributes:
        enable_es_text: Enable Elasticsearch text index
        enable_es_vector: Enable Elasticsearch vector index
        enable_milvus: Enable Milvus vector store
        enable_clickhouse: Enable ClickHouse analytics store
    """

    enable_es_text: bool = True
    enable_es_vector: bool = False
    enable_milvus: bool = True
    enable_clickhouse: bool = True


class PipelineConfigs(BaseModel):
    """Aggregated configuration for all pipeline stages.

    Attributes:
        clean: Text cleaning configuration
        i2t: Image-to-text configuration
        split: Text splitting configuration
        keywords: Keyword extraction configuration
        qa: Question-answer generation configuration
        summary: Summarization configuration
        embed: Embedding generation configuration
        index: Indexing configuration
    """

    clean: CleanConfig = Field(default_factory=CleanConfig)
    i2t: I2tConfig = Field(default_factory=I2tConfig)
    split: SplitConfig = Field(default_factory=SplitConfig)
    keywords: KeywordsConfig = Field(default_factory=KeywordsConfig)
    qa: QaConfig = Field(default_factory=QaConfig)
    summary: SummaryConfig = Field(default_factory=SummaryConfig)
    embed: EmbedConfig = Field(default_factory=EmbedConfig)
    index: IndexConfig = Field(default_factory=IndexConfig)


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Uses pydantic-settings for type-safe configuration loading with
    automatic environment variable parsing and validation.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = Field(
        default="mysql+aiomysql://root:password@localhost:3306/deep_parser",
        description="Database connection URL"
    )

    # Elasticsearch
    es_hosts: str = Field(
        default="http://localhost:9200",
        description="Elasticsearch hosts"
    )
    es_username: str = Field(
        default="",
        description="Elasticsearch username"
    )
    es_password: str = Field(
        default="",
        description="Elasticsearch password"
    )

    # Milvus
    milvus_host: str = Field(
        default="localhost",
        description="Milvus host"
    )
    milvus_port: int = Field(
        default=19530,
        description="Milvus port"
    )

    # ClickHouse
    clickhouse_host: str = Field(
        default="localhost",
        description="ClickHouse host"
    )
    clickhouse_port: int = Field(
        default=8123,
        description="ClickHouse port"
    )
    clickhouse_user: str = Field(
        default="default",
        description="ClickHouse user"
    )
    clickhouse_password: str = Field(
        default="",
        description="ClickHouse password"
    )

    # LLM Provider
    llm_provider: str = Field(
        default="openai",
        description="LLM provider name"
    )
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key"
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI base URL"
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model name"
    )

    # Embedding Provider
    embedding_provider: str = Field(
        default="openai",
        description="Embedding provider name"
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Embedding model name"
    )
    embedding_dim: int = Field(
        default=1536,
        description="Embedding dimension"
    )

    # I2T Provider
    i2t_provider: str = Field(
        default="openai",
        description="Image-to-text provider name"
    )
    i2t_model: str = Field(
        default="gpt-4o-mini",
        description="Image-to-text model name"
    )

    # Storage
    storage_base_path: str = Field(
        default="./data/storage",
        description="Base path for file storage"
    )
    image_host_base_url: str = Field(
        default="http://localhost:8000/api/images",
        description="Base URL for image hosting"
    )

    # Airflow
    airflow_base_url: str = Field(
        default="http://localhost:8080",
        description="Airflow base URL"
    )

    # Server
    server_host: str = Field(
        default="0.0.0.0",
        description="Server host"
    )
    server_port: int = Field(
        default=8000,
        description="Server port"
    )

    @field_validator("server_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate server port is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v


def get_config_dir() -> Path:
    """Get the configuration directory path.

    Returns:
        Path object pointing to the config directory
    """
    current_dir = Path(__file__).parent.parent.parent
    return current_dir / "config"


def load_yaml_config(config_name: str) -> Dict[str, Any]:
    """Load a YAML configuration file from the config directory.

    Args:
        config_name: Name of the YAML file without extension (e.g., 'clean')

    Returns:
        Dictionary containing the loaded configuration

    Raises:
        FileNotFoundError: If the configuration file does not exist
        yaml.YAMLError: If the YAML file is malformed
    """
    config_dir = get_config_dir()
    config_path = config_dir / f"{config_name}.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_pipeline_config() -> PipelineConfigs:
    """Load and aggregate all pipeline configurations.

    Returns:
        PipelineConfigs object containing all stage configurations

    Raises:
        FileNotFoundError: If any required configuration file is missing
        pydantic.ValidationError: If any configuration is invalid
    """
    configs: Dict[str, Any] = {}

    config_mappings = {
        "clean": CleanConfig,
        "i2t": I2tConfig,
        "split": SplitConfig,
        "keywords": KeywordsConfig,
        "qa": QaConfig,
        "summary": SummaryConfig,
        "embed": EmbedConfig,
        "index": IndexConfig,
    }

    for config_name, config_class in config_mappings.items():
        config_data = load_yaml_config(config_name)
        configs[config_name] = config_class(**config_data)

    return PipelineConfigs(**configs)


@lru_cache
def get_settings() -> Settings:
    """Get cached Settings singleton instance.

    Uses lru_cache to ensure only one Settings instance is created
    and reused throughout the application lifecycle.

    Returns:
        Settings instance loaded from environment variables
    """
    return Settings()
