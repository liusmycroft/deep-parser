"""Property-based tests for configuration management.

Feature: rag-testing-system
"""

import os
import json
import tempfile
from pathlib import Path
import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck

from rag_testing_system.config import (
    load_config,
    ConfigLoader,
    ConfigurationError,
    RAGSystemConfig,
    LogLevel,
)


# Strategies for generating test data
@st.composite
def valid_config_dict(draw):
    """Generate a valid configuration dictionary."""
    return {
        "database": {
            "elasticsearch": {
                "hosts": draw(st.lists(st.text(min_size=10, max_size=50), min_size=1, max_size=3)),
                "index_name": draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='_-'))),
                "shards": draw(st.integers(min_value=1, max_value=10)),
                "replicas": draw(st.integers(min_value=0, max_value=5)),
            }
        },
        "processing": {
            "chunk_size": draw(st.integers(min_value=1, max_value=10000)),
            "chunk_overlap": draw(st.integers(min_value=0, max_value=1000)),
        },
        "embedding": {
            "batch_size": draw(st.integers(min_value=1, max_value=128)),
        }
    }


@st.composite
def env_var_name(draw):
    """Generate valid environment variable names."""
    # RAG_SECTION__SUBSECTION__KEY format
    sections = ["DATABASE", "PROCESSING", "EMBEDDING", "LOGGING", "WEB"]
    section = draw(st.sampled_from(sections))
    
    subsections = {
        "DATABASE": ["ELASTICSEARCH", "MILVUS", "CLICKHOUSE", "HBASE"],
        "PROCESSING": [""],
        "EMBEDDING": [""],
        "LOGGING": [""],
        "WEB": [""],
    }
    
    subsection = draw(st.sampled_from(subsections[section]))
    
    keys = {
        "ELASTICSEARCH": ["HOSTS", "INDEX_NAME", "SHARDS", "REPLICAS"],
        "MILVUS": ["HOST", "PORT", "COLLECTION_NAME"],
        "CLICKHOUSE": ["HOST", "PORT", "DATABASE"],
        "HBASE": ["HOST", "PORT", "TABLE_NAME"],
        "": ["CHUNK_SIZE", "BATCH_SIZE", "LEVEL", "PORT"],
    }
    
    key = draw(st.sampled_from(keys.get(subsection, ["VALUE"])))
    
    if subsection:
        return f"RAG_{section}__{subsection}__{key}"
    else:
        return f"RAG_{section}__{key}"


class TestConfigurationLoadingProperties:
    """Property-based tests for configuration loading.
    
    Feature: rag-testing-system, Property 37: Multi-source configuration loading
    Validates: Requirements 11.1
    """

    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(config_data=valid_config_dict())
    @pytest.mark.property
    def test_property_37_file_config_loading(self, config_data, tmp_path):
        """
        Property 37: Multi-source configuration loading
        
        For any valid configuration dictionary, loading from a file should
        produce a configuration with those values accessible.
        
        **Validates: Requirements 11.1**
        """
        # Create config file
        config_file = tmp_path / "config.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        # Load configuration
        config = load_config(config_file=str(config_file), load_env=False)
        
        # Verify values are accessible
        if "database" in config_data and "elasticsearch" in config_data["database"]:
            es_config = config_data["database"]["elasticsearch"]
            if "hosts" in es_config:
                assert config.database.elasticsearch.hosts == es_config["hosts"]
            if "index_name" in es_config:
                assert config.database.elasticsearch.index_name == es_config["index_name"]
            if "shards" in es_config:
                assert config.database.elasticsearch.shards == es_config["shards"]
        
        if "processing" in config_data:
            proc_config = config_data["processing"]
            if "chunk_size" in proc_config:
                assert config.processing.chunk_size == proc_config["chunk_size"]
            if "chunk_overlap" in proc_config:
                assert config.processing.chunk_overlap == proc_config["chunk_overlap"]

    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        chunk_size=st.integers(min_value=1, max_value=10000),
        index_name=st.text(
            min_size=2, 
            max_size=50, 
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu'), whitelist_characters='_-')
        ).filter(lambda x: not x.isdigit() and x.lower() not in ['infinity', 'nan', 'true', 'false', 'null'])
    )
    @pytest.mark.property
    def test_property_37_env_config_loading(self, chunk_size, index_name, monkeypatch):
        """
        Property 37: Multi-source configuration loading (environment variables)
        
        For any valid configuration values, setting them as environment variables
        should result in those values being loaded into the configuration.
        
        **Validates: Requirements 11.1**
        """
        # Set environment variables
        monkeypatch.setenv("RAG_PROCESSING__CHUNK_SIZE", str(chunk_size))
        monkeypatch.setenv("RAG_DATABASE__ELASTICSEARCH__INDEX_NAME", index_name)
        
        # Load configuration
        config = load_config(load_env=True)
        
        # Verify values were loaded
        assert config.processing.chunk_size == chunk_size
        assert config.database.elasticsearch.index_name == index_name

    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        file_chunk_size=st.integers(min_value=1, max_value=5000),
        env_chunk_size=st.integers(min_value=5001, max_value=10000)
    )
    @pytest.mark.property
    def test_property_37_precedence_order(self, file_chunk_size, env_chunk_size, tmp_path, monkeypatch):
        """
        Property 37: Multi-source configuration loading (precedence)
        
        For any configuration values from different sources, environment variables
        should take precedence over file configuration.
        
        **Validates: Requirements 11.1**
        """
        # Ensure values are different
        assume(file_chunk_size != env_chunk_size)
        
        # Create config file
        config_file = tmp_path / "config.json"
        with open(config_file, 'w') as f:
            json.dump({"processing": {"chunk_size": file_chunk_size}}, f)
        
        # Set environment variable (should override file)
        monkeypatch.setenv("RAG_PROCESSING__CHUNK_SIZE", str(env_chunk_size))
        
        # Load configuration
        config = load_config(config_file=str(config_file), load_env=True)
        
        # Environment variable should take precedence
        assert config.processing.chunk_size == env_chunk_size
        assert config.processing.chunk_size != file_chunk_size

    @settings(max_examples=50)
    @given(
        chunk_size=st.integers(min_value=1, max_value=10000),
        batch_size=st.integers(min_value=1, max_value=128)
    )
    @pytest.mark.property
    def test_property_37_cli_args_loading(self, chunk_size, batch_size):
        """
        Property 37: Multi-source configuration loading (command-line arguments)
        
        For any valid configuration values, providing them as command-line arguments
        should result in those values being loaded into the configuration.
        
        **Validates: Requirements 11.1**
        """
        import argparse
        
        # Create args namespace simulating command-line arguments
        args = argparse.Namespace(
            chunk_size=chunk_size,
            embedding_batch_size=batch_size,
            config=None,
            elasticsearch_hosts=None,
            milvus_host=None,
            clickhouse_host=None,
            hbase_host=None,
            embedding_model=None,
            chunk_overlap=None,
            log_level=None,
            log_file=None,
            web_host=None,
            web_port=None
        )
        
        # Load configuration with CLI args
        loader = ConfigLoader()
        loader.load_from_args(args)
        config = loader.build()
        
        # Verify values were loaded
        assert config.processing.chunk_size == chunk_size
        assert config.embedding.batch_size == batch_size

    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        file_chunk_size=st.integers(min_value=1, max_value=3000),
        env_chunk_size=st.integers(min_value=3001, max_value=6000),
        cli_chunk_size=st.integers(min_value=6001, max_value=10000)
    )
    @pytest.mark.property
    def test_property_37_full_precedence_order(self, file_chunk_size, env_chunk_size, cli_chunk_size, tmp_path, monkeypatch):
        """
        Property 37: Multi-source configuration loading (full precedence)
        
        For any configuration values from all sources, command-line arguments
        should take precedence over environment variables, which should take
        precedence over file configuration.
        
        **Validates: Requirements 11.1**
        """
        import argparse
        
        # Ensure all values are different
        assume(file_chunk_size != env_chunk_size)
        assume(env_chunk_size != cli_chunk_size)
        assume(file_chunk_size != cli_chunk_size)
        
        # Create config file
        config_file = tmp_path / "config.json"
        with open(config_file, 'w') as f:
            json.dump({"processing": {"chunk_size": file_chunk_size}}, f)
        
        # Set environment variable
        monkeypatch.setenv("RAG_PROCESSING__CHUNK_SIZE", str(env_chunk_size))
        
        # Create CLI args
        args = argparse.Namespace(
            chunk_size=cli_chunk_size,
            config=None,
            elasticsearch_hosts=None,
            milvus_host=None,
            clickhouse_host=None,
            hbase_host=None,
            embedding_model=None,
            embedding_batch_size=None,
            chunk_overlap=None,
            log_level=None,
            log_file=None,
            web_host=None,
            web_port=None
        )
        
        # Load configuration from all sources
        loader = ConfigLoader()
        loader.load_from_file(str(config_file))
        loader.load_from_env()
        loader.load_from_args(args)
        config = loader.build()
        
        # CLI args should take precedence over everything
        assert config.processing.chunk_size == cli_chunk_size
        assert config.processing.chunk_size != env_chunk_size
        assert config.processing.chunk_size != file_chunk_size


class TestConfigurationValidationProperties:
    """Property-based tests for configuration validation.
    
    Feature: rag-testing-system, Property 39: Configuration validation
    Validates: Requirements 11.5
    """

    @settings(max_examples=50)
    @given(chunk_size=st.integers(max_value=0))
    @pytest.mark.property
    def test_property_39_invalid_chunk_size(self, chunk_size):
        """
        Property 39: Configuration validation
        
        For any chunk_size <= 0, the configuration validation should fail
        with a clear error message.
        
        **Validates: Requirements 11.5**
        """
        loader = ConfigLoader()
        loader._config_dict = {
            "processing": {
                "chunk_size": chunk_size
            }
        }
        
        with pytest.raises(ConfigurationError, match="validation failed"):
            loader.build()

    @settings(max_examples=50)
    @given(shards=st.integers(max_value=0))
    @pytest.mark.property
    def test_property_39_invalid_shards(self, shards):
        """
        Property 39: Configuration validation
        
        For any shards <= 0, the configuration validation should fail
        with a clear error message.
        
        **Validates: Requirements 11.5**
        """
        loader = ConfigLoader()
        loader._config_dict = {
            "database": {
                "elasticsearch": {
                    "shards": shards
                }
            }
        }
        
        with pytest.raises(ConfigurationError, match="validation failed"):
            loader.build()

    @settings(max_examples=50)
    @given(replicas=st.integers(max_value=-1))
    @pytest.mark.property
    def test_property_39_invalid_replicas(self, replicas):
        """
        Property 39: Configuration validation
        
        For any replicas < 0, the configuration validation should fail
        with a clear error message.
        
        **Validates: Requirements 11.5**
        """
        loader = ConfigLoader()
        loader._config_dict = {
            "database": {
                "elasticsearch": {
                    "replicas": replicas
                }
            }
        }
        
        with pytest.raises(ConfigurationError, match="validation failed"):
            loader.build()

    @settings(max_examples=50)
    @given(port=st.integers().filter(lambda x: x < 1 or x > 65535))
    @pytest.mark.property
    def test_property_39_invalid_port(self, port):
        """
        Property 39: Configuration validation
        
        For any port outside the valid range [1, 65535], the configuration
        validation should fail with a clear error message.
        
        **Validates: Requirements 11.5**
        """
        loader = ConfigLoader()
        loader._config_dict = {
            "database": {
                "milvus": {
                    "port": port
                }
            }
        }
        
        with pytest.raises(ConfigurationError, match="validation failed"):
            loader.build()

    @settings(max_examples=50)
    @given(
        chunk_size=st.integers(min_value=1, max_value=10000),
        chunk_overlap=st.integers(min_value=0, max_value=1000),
        shards=st.integers(min_value=1, max_value=10),
        replicas=st.integers(min_value=0, max_value=5),
        port=st.integers(min_value=1, max_value=65535)
    )
    @pytest.mark.property
    def test_property_39_valid_config_accepted(self, chunk_size, chunk_overlap, shards, replicas, port):
        """
        Property 39: Configuration validation (positive case)
        
        For any valid configuration values, the configuration validation
        should succeed and produce a valid RAGSystemConfig instance.
        
        **Validates: Requirements 11.5**
        """
        loader = ConfigLoader()
        loader._config_dict = {
            "processing": {
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap
            },
            "database": {
                "elasticsearch": {
                    "shards": shards,
                    "replicas": replicas
                },
                "milvus": {
                    "port": port
                }
            }
        }
        
        # Should not raise an exception
        config = loader.build()
        
        # Verify values are set correctly
        assert isinstance(config, RAGSystemConfig)
        assert config.processing.chunk_size == chunk_size
        assert config.processing.chunk_overlap == chunk_overlap
        assert config.database.elasticsearch.shards == shards
        assert config.database.elasticsearch.replicas == replicas
        assert config.database.milvus.port == port

    @settings(max_examples=30)
    @given(invalid_path=st.text(min_size=1, max_size=100).filter(lambda x: not Path(x).exists()))
    @pytest.mark.property
    def test_property_39_nonexistent_file_error(self, invalid_path):
        """
        Property 39: Configuration validation (file errors)
        
        For any non-existent file path, attempting to load configuration
        should fail with a clear error message indicating the file was not found.
        
        **Validates: Requirements 11.5**
        """
        with pytest.raises(ConfigurationError, match="Configuration file not found"):
            load_config(config_file=invalid_path, load_env=False)

    @settings(max_examples=50)
    @given(
        chunk_overlap=st.integers(min_value=1, max_value=10000),
        chunk_size=st.integers(min_value=1, max_value=10000)
    )
    @pytest.mark.property
    def test_property_39_chunk_overlap_exceeds_chunk_size(self, chunk_overlap, chunk_size):
        """
        Property 39: Configuration validation (logical constraints)
        
        For any chunk_overlap >= chunk_size, the configuration should be accepted
        (the system should handle this edge case gracefully).
        
        **Validates: Requirements 11.5**
        """
        # This tests that the system accepts edge cases where overlap >= size
        # The actual chunking logic should handle this appropriately
        loader = ConfigLoader()
        loader._config_dict = {
            "processing": {
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap
            }
        }
        
        # Should not raise an exception - validation allows this
        config = loader.build()
        assert config.processing.chunk_size == chunk_size
        assert config.processing.chunk_overlap == chunk_overlap

    @settings(max_examples=50)
    @given(invalid_log_level=st.text(min_size=1, max_size=20).filter(
        lambda x: x.upper() not in ['DEBUG', 'INFO', 'WARNING', 'ERROR']
    ))
    @pytest.mark.property
    def test_property_39_invalid_log_level(self, invalid_log_level):
        """
        Property 39: Configuration validation (enum validation)
        
        For any log level that is not one of the valid values (DEBUG, INFO, WARNING, ERROR),
        the configuration validation should fail with a clear error message.
        
        **Validates: Requirements 11.5**
        """
        loader = ConfigLoader()
        loader._config_dict = {
            "logging": {
                "level": invalid_log_level
            }
        }
        
        with pytest.raises(ConfigurationError, match="validation failed"):
            loader.build()

    @settings(max_examples=50)
    @given(
        batch_size=st.integers(max_value=0)
    )
    @pytest.mark.property
    def test_property_39_invalid_batch_size(self, batch_size):
        """
        Property 39: Configuration validation (batch size)
        
        For any batch_size <= 0, the configuration validation should fail
        with a clear error message.
        
        **Validates: Requirements 11.5**
        """
        loader = ConfigLoader()
        loader._config_dict = {
            "embedding": {
                "batch_size": batch_size
            }
        }
        
        with pytest.raises(ConfigurationError, match="validation failed"):
            loader.build()

    @settings(max_examples=50)
    @given(
        embedding_dim=st.integers(max_value=0)
    )
    @pytest.mark.property
    def test_property_39_invalid_embedding_dim(self, embedding_dim):
        """
        Property 39: Configuration validation (embedding dimension)
        
        For any embedding_dim <= 0, the configuration validation should fail
        with a clear error message.
        
        **Validates: Requirements 11.5**
        """
        loader = ConfigLoader()
        loader._config_dict = {
            "embedding": {
                "embedding_dim": embedding_dim
            }
        }
        
        with pytest.raises(ConfigurationError, match="validation failed"):
            loader.build()

    @settings(max_examples=50)
    @given(
        top_k=st.integers(max_value=0)
    )
    @pytest.mark.property
    def test_property_39_invalid_top_k(self, top_k):
        """
        Property 39: Configuration validation (retrieval top_k)
        
        For any default_top_k <= 0, the configuration validation should fail
        with a clear error message.
        
        **Validates: Requirements 11.5**
        """
        loader = ConfigLoader()
        loader._config_dict = {
            "retrieval": {
                "default_top_k": top_k
            }
        }
        
        with pytest.raises(ConfigurationError, match="validation failed"):
            loader.build()

    @settings(max_examples=50)
    @given(
        score_threshold=st.floats(allow_nan=False, allow_infinity=False).filter(
            lambda x: x < 0.0 or x > 1.0
        )
    )
    @pytest.mark.property
    def test_property_39_invalid_score_threshold(self, score_threshold):
        """
        Property 39: Configuration validation (score threshold range)
        
        For any score_threshold outside [0.0, 1.0], the configuration validation
        should fail with a clear error message.
        
        **Validates: Requirements 11.5**
        """
        loader = ConfigLoader()
        loader._config_dict = {
            "retrieval": {
                "default_score_threshold": score_threshold
            }
        }
        
        with pytest.raises(ConfigurationError, match="validation failed"):
            loader.build()

    @settings(max_examples=50)
    @given(
        hybrid_weight=st.floats(allow_nan=False, allow_infinity=False).filter(
            lambda x: x < 0.0 or x > 1.0
        )
    )
    @pytest.mark.property
    def test_property_39_invalid_hybrid_weight(self, hybrid_weight):
        """
        Property 39: Configuration validation (hybrid weight range)
        
        For any elasticsearch_hybrid_weight outside [0.0, 1.0], the configuration
        validation should fail with a clear error message.
        
        **Validates: Requirements 11.5**
        """
        loader = ConfigLoader()
        loader._config_dict = {
            "retrieval": {
                "elasticsearch_hybrid_weight": hybrid_weight
            }
        }
        
        with pytest.raises(ConfigurationError, match="validation failed"):
            loader.build()

    @settings(max_examples=50)
    @given(
        qps=st.integers(max_value=0)
    )
    @pytest.mark.property
    def test_property_39_invalid_qps(self, qps):
        """
        Property 39: Configuration validation (performance QPS)
        
        For any default_qps <= 0, the configuration validation should fail
        with a clear error message.
        
        **Validates: Requirements 11.5**
        """
        loader = ConfigLoader()
        loader._config_dict = {
            "performance": {
                "default_qps": qps
            }
        }
        
        with pytest.raises(ConfigurationError, match="validation failed"):
            loader.build()

    @settings(max_examples=50)
    @given(
        duration=st.integers(max_value=0)
    )
    @pytest.mark.property
    def test_property_39_invalid_duration(self, duration):
        """
        Property 39: Configuration validation (test duration)
        
        For any default_duration <= 0, the configuration validation should fail
        with a clear error message.
        
        **Validates: Requirements 11.5**
        """
        loader = ConfigLoader()
        loader._config_dict = {
            "performance": {
                "default_duration": duration
            }
        }
        
        with pytest.raises(ConfigurationError, match="validation failed"):
            loader.build()

    @settings(max_examples=50)
    @given(
        concurrency=st.integers(max_value=0)
    )
    @pytest.mark.property
    def test_property_39_invalid_concurrency(self, concurrency):
        """
        Property 39: Configuration validation (concurrency)
        
        For any default_concurrency <= 0, the configuration validation should fail
        with a clear error message.
        
        **Validates: Requirements 11.5**
        """
        loader = ConfigLoader()
        loader._config_dict = {
            "performance": {
                "default_concurrency": concurrency
            }
        }
        
        with pytest.raises(ConfigurationError, match="validation failed"):
            loader.build()

    @settings(max_examples=50)
    @given(
        max_retries=st.integers(max_value=-1)
    )
    @pytest.mark.property
    def test_property_39_invalid_max_retries(self, max_retries):
        """
        Property 39: Configuration validation (workflow retries)
        
        For any max_retries < 0, the configuration validation should fail
        with a clear error message.
        
        **Validates: Requirements 11.5**
        """
        loader = ConfigLoader()
        loader._config_dict = {
            "workflow": {
                "max_retries": max_retries
            }
        }
        
        with pytest.raises(ConfigurationError, match="validation failed"):
            loader.build()

    @settings(max_examples=50)
    @given(
        web_port=st.integers().filter(lambda x: x < 1 or x > 65535)
    )
    @pytest.mark.property
    def test_property_39_invalid_web_port(self, web_port):
        """
        Property 39: Configuration validation (web port)
        
        For any web port outside the valid range [1, 65535], the configuration
        validation should fail with a clear error message.
        
        **Validates: Requirements 11.5**
        """
        loader = ConfigLoader()
        loader._config_dict = {
            "web": {
                "port": web_port
            }
        }
        
        with pytest.raises(ConfigurationError, match="validation failed"):
            loader.build()

    @settings(max_examples=50)
    @given(
        clickhouse_port=st.integers().filter(lambda x: x < 1 or x > 65535)
    )
    @pytest.mark.property
    def test_property_39_invalid_clickhouse_port(self, clickhouse_port):
        """
        Property 39: Configuration validation (ClickHouse port)
        
        For any ClickHouse port outside the valid range [1, 65535], the configuration
        validation should fail with a clear error message.
        
        **Validates: Requirements 11.5**
        """
        loader = ConfigLoader()
        loader._config_dict = {
            "database": {
                "clickhouse": {
                    "port": clickhouse_port
                }
            }
        }
        
        with pytest.raises(ConfigurationError, match="validation failed"):
            loader.build()

    @settings(max_examples=50)
    @given(
        hbase_port=st.integers().filter(lambda x: x < 1 or x > 65535)
    )
    @pytest.mark.property
    def test_property_39_invalid_hbase_port(self, hbase_port):
        """
        Property 39: Configuration validation (HBase port)
        
        For any HBase port outside the valid range [1, 65535], the configuration
        validation should fail with a clear error message.
        
        **Validates: Requirements 11.5**
        """
        loader = ConfigLoader()
        loader._config_dict = {
            "database": {
                "hbase": {
                    "port": hbase_port
                }
            }
        }
        
        with pytest.raises(ConfigurationError, match="validation failed"):
            loader.build()
