"""Pytest configuration and shared fixtures."""

import pytest
from pathlib import Path
from typing import Dict, Any

from rag_testing_system.config.models import (
    RAGSystemConfig,
    LoggingConfig,
    LogLevel,
)


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for configuration files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def default_config() -> RAGSystemConfig:
    """Provide a default configuration for testing."""
    return RAGSystemConfig()


@pytest.fixture
def test_logging_config() -> LoggingConfig:
    """Provide a test logging configuration."""
    return LoggingConfig(
        level=LogLevel.DEBUG,
        format="json",
        enable_console=False,  # Disable console for tests
        output_file=None
    )


@pytest.fixture
def sample_config_dict() -> Dict[str, Any]:
    """Provide a sample configuration dictionary."""
    return {
        "database": {
            "elasticsearch": {
                "hosts": ["http://test-es:9200"],
                "index_name": "test_index"
            },
            "milvus": {
                "host": "test-milvus",
                "port": 19530
            }
        },
        "embedding": {
            "model_name": "test-model",
            "batch_size": 16
        },
        "processing": {
            "chunk_size": 256,
            "chunk_overlap": 25
        },
        "logging": {
            "level": "DEBUG",
            "format": "json"
        }
    }
