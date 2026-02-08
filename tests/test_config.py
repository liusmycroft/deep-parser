"""Tests for configuration management."""

import os
import json
import tempfile
from pathlib import Path
import pytest

from rag_testing_system.config import (
    load_config,
    ConfigLoader,
    ConfigurationError,
    RAGSystemConfig,
    LogLevel,
)


class TestConfigLoader:
    """Test configuration loading from multiple sources."""

    def test_default_config(self):
        """Test that default configuration can be created."""
        config = RAGSystemConfig()
        
        assert config.database.elasticsearch.hosts == ["http://localhost:9200"]
        assert config.embedding.model_name == "sentence-transformers/all-MiniLM-L6-v2"
        assert config.processing.chunk_size == 512
        assert config.logging.level == LogLevel.INFO

    def test_load_from_yaml_file(self, tmp_path):
        """Test loading configuration from YAML file."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "database": {
                "elasticsearch": {
                    "hosts": ["http://test:9200"],
                    "index_name": "test_index"
                }
            },
            "processing": {
                "chunk_size": 256
            }
        }
        
        with open(config_file, 'w') as f:
            import yaml
            yaml.dump(config_data, f)
        
        config = load_config(config_file=str(config_file), load_env=False)
        
        assert config.database.elasticsearch.hosts == ["http://test:9200"]
        assert config.database.elasticsearch.index_name == "test_index"
        assert config.processing.chunk_size == 256

    def test_load_from_json_file(self, tmp_path):
        """Test loading configuration from JSON file."""
        config_file = tmp_path / "config.json"
        config_data = {
            "embedding": {
                "model_name": "test-model",
                "batch_size": 16
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        config = load_config(config_file=str(config_file), load_env=False)
        
        assert config.embedding.model_name == "test-model"
        assert config.embedding.batch_size == 16

    def test_load_from_env_variables(self, monkeypatch):
        """Test loading configuration from environment variables."""
        monkeypatch.setenv("RAG_DATABASE__ELASTICSEARCH__INDEX_NAME", "env_index")
        monkeypatch.setenv("RAG_PROCESSING__CHUNK_SIZE", "1024")
        monkeypatch.setenv("RAG_LOGGING__LEVEL", "DEBUG")
        
        config = load_config(load_env=True)
        
        assert config.database.elasticsearch.index_name == "env_index"
        assert config.processing.chunk_size == 1024
        assert config.logging.level == LogLevel.DEBUG

    def test_env_variables_with_json_values(self, monkeypatch):
        """Test environment variables with JSON values."""
        monkeypatch.setenv(
            "RAG_DATABASE__ELASTICSEARCH__HOSTS",
            '["http://es1:9200", "http://es2:9200"]'
        )
        
        config = load_config(load_env=True)
        
        assert config.database.elasticsearch.hosts == [
            "http://es1:9200",
            "http://es2:9200"
        ]

    def test_configuration_precedence(self, tmp_path, monkeypatch):
        """Test that configuration sources have correct precedence."""
        # Create config file
        config_file = tmp_path / "config.yaml"
        with open(config_file, 'w') as f:
            import yaml
            yaml.dump({"processing": {"chunk_size": 256}}, f)
        
        # Set environment variable (should override file)
        monkeypatch.setenv("RAG_PROCESSING__CHUNK_SIZE", "512")
        
        config = load_config(config_file=str(config_file), load_env=True)
        
        # Environment variable should take precedence
        assert config.processing.chunk_size == 512

    def test_invalid_config_file_path(self):
        """Test error handling for non-existent config file."""
        with pytest.raises(ConfigurationError, match="Configuration file not found"):
            load_config(config_file="/nonexistent/config.yaml", load_env=False)

    def test_invalid_yaml_syntax(self, tmp_path):
        """Test error handling for invalid YAML syntax."""
        config_file = tmp_path / "bad_config.yaml"
        with open(config_file, 'w') as f:
            f.write("invalid: yaml: syntax: [")
        
        with pytest.raises(ConfigurationError, match="Failed to parse"):
            load_config(config_file=str(config_file), load_env=False)

    def test_invalid_config_values(self):
        """Test validation of invalid configuration values."""
        loader = ConfigLoader()
        loader._config_dict = {
            "processing": {
                "chunk_size": -1  # Invalid: must be >= 1
            }
        }
        
        with pytest.raises(ConfigurationError, match="validation failed"):
            loader.build()

    def test_nested_config_merge(self, tmp_path):
        """Test that nested configurations are properly merged."""
        config_file = tmp_path / "config.yaml"
        with open(config_file, 'w') as f:
            import yaml
            yaml.dump({
                "database": {
                    "elasticsearch": {
                        "hosts": ["http://file:9200"]
                    }
                }
            }, f)
        
        loader = ConfigLoader()
        loader.load_from_file(str(config_file))
        
        # Add more config that should merge, not replace
        loader._merge_config({
            "database": {
                "elasticsearch": {
                    "index_name": "merged_index"
                },
                "milvus": {
                    "host": "milvus-host"
                }
            }
        })
        
        config = loader.build()
        
        # Both values should be present
        assert config.database.elasticsearch.hosts == ["http://file:9200"]
        assert config.database.elasticsearch.index_name == "merged_index"
        assert config.database.milvus.host == "milvus-host"


class TestConfigModels:
    """Test configuration model validation."""

    def test_elasticsearch_config_validation(self):
        """Test Elasticsearch configuration validation."""
        from rag_testing_system.config.models import ElasticsearchConfig
        
        # Valid config
        config = ElasticsearchConfig(
            hosts=["http://localhost:9200"],
            shards=2,
            replicas=1
        )
        assert config.shards == 2
        
        # Invalid: shards must be >= 1
        with pytest.raises(Exception):
            ElasticsearchConfig(shards=0)

    def test_milvus_config_validation(self):
        """Test Milvus configuration validation."""
        from rag_testing_system.config.models import MilvusConfig
        
        config = MilvusConfig(
            host="localhost",
            port=19530,
            index_type="HNSW",
            metric_type="COSINE"
        )
        assert config.index_type == "HNSW"
        assert config.metric_type == "COSINE"

    def test_processing_config_validation(self):
        """Test processing configuration validation."""
        from rag_testing_system.config.models import ProcessingConfig
        
        config = ProcessingConfig(
            chunk_size=512,
            chunk_overlap=50
        )
        assert config.chunk_size == 512
        assert config.chunk_overlap == 50
        
        # Invalid: chunk_size must be >= 1
        with pytest.raises(Exception):
            ProcessingConfig(chunk_size=0)

    def test_logging_config_validation(self):
        """Test logging configuration validation."""
        from rag_testing_system.config.models import LoggingConfig
        
        config = LoggingConfig(
            level=LogLevel.DEBUG,
            format="json"
        )
        assert config.level == LogLevel.DEBUG
        assert config.format == "json"
