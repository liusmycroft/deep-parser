"""Configuration loader with support for files, environment variables, and CLI arguments."""

import os
import json
import yaml
import argparse
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

from .models import RAGSystemConfig


class ConfigurationError(Exception):
    """Raised when configuration is invalid or cannot be loaded."""
    pass


class ConfigLoader:
    """
    Load configuration from multiple sources with precedence:
    1. Command-line arguments (highest priority)
    2. Environment variables
    3. Configuration file
    4. Default values (lowest priority)
    """

    def __init__(self) -> None:
        """Initialize the configuration loader."""
        self._config_dict: Dict[str, Any] = {}

    def load_from_file(self, file_path: str) -> "ConfigLoader":
        """
        Load configuration from a YAML or JSON file.

        Args:
            file_path: Path to the configuration file

        Returns:
            Self for method chaining

        Raises:
            ConfigurationError: If file cannot be read or parsed
        """
        path = Path(file_path)
        
        if not path.exists():
            raise ConfigurationError(f"Configuration file not found: {file_path}")
        
        if not path.is_file():
            raise ConfigurationError(f"Configuration path is not a file: {file_path}")
        
        try:
            with open(path, 'r') as f:
                if path.suffix in ['.yaml', '.yml']:
                    file_config = yaml.safe_load(f)
                elif path.suffix == '.json':
                    file_config = json.load(f)
                else:
                    raise ConfigurationError(
                        f"Unsupported configuration file format: {path.suffix}. "
                        "Use .yaml, .yml, or .json"
                    )
            
            if file_config is None:
                file_config = {}
            
            self._merge_config(file_config)
            return self
            
        except (yaml.YAMLError, json.JSONDecodeError) as e:
            raise ConfigurationError(f"Failed to parse configuration file: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to read configuration file: {e}")

    def load_from_env(self, prefix: str = "RAG_") -> "ConfigLoader":
        """
        Load configuration from environment variables.

        Environment variables should be prefixed (default: RAG_) and use
        double underscores to indicate nesting. For example:
        - RAG_DATABASE__ELASTICSEARCH__HOSTS=http://localhost:9200
        - RAG_EMBEDDING__MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2

        Args:
            prefix: Prefix for environment variables (default: RAG_)

        Returns:
            Self for method chaining
        """
        # Load .env file if it exists
        load_dotenv()
        
        env_config: Dict[str, Any] = {}
        
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            
            # Remove prefix and convert to lowercase
            config_key = key[len(prefix):].lower()
            
            # Split by double underscore to handle nesting
            parts = config_key.split('__')
            
            # Build nested dictionary
            current = env_config
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Set the value, attempting to parse JSON for complex types
            final_key = parts[-1]
            try:
                # Try to parse as JSON (for lists, dicts, numbers, booleans)
                current[final_key] = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                # Keep as string if not valid JSON
                current[final_key] = value
        
        self._merge_config(env_config)
        return self

    def load_from_args(self, args: Optional[argparse.Namespace] = None) -> "ConfigLoader":
        """
        Load configuration from command-line arguments.

        Args:
            args: Parsed arguments namespace. If None, will parse sys.argv

        Returns:
            Self for method chaining
        """
        if args is None:
            parser = self._create_argument_parser()
            args = parser.parse_args()
        
        # Convert args namespace to dictionary, filtering out None values
        args_dict = {k: v for k, v in vars(args).items() if v is not None}
        
        # Map CLI argument names to nested configuration structure
        nested_config = self._map_args_to_config(args_dict)
        
        self._merge_config(nested_config)
        return self

    def build(self) -> RAGSystemConfig:
        """
        Build and validate the final configuration.

        Returns:
            Validated RAGSystemConfig instance

        Raises:
            ConfigurationError: If configuration is invalid
        """
        try:
            config = RAGSystemConfig(**self._config_dict)
            return config
        except Exception as e:
            raise ConfigurationError(f"Configuration validation failed: {e}")

    def _merge_config(self, new_config: Dict[str, Any]) -> None:
        """
        Merge new configuration into existing config.

        Args:
            new_config: New configuration dictionary to merge
        """
        self._deep_merge(self._config_dict, new_config)

    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> None:
        """
        Recursively merge update dict into base dict.

        Args:
            base: Base dictionary to update
            update: Dictionary with updates
        """
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def _flatten_to_nested(self, flat_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert flat dictionary with underscores to nested structure.

        Args:
            flat_dict: Flat dictionary with keys like 'database_elasticsearch_hosts'

        Returns:
            Nested dictionary
        """
        nested: Dict[str, Any] = {}
        
        for key, value in flat_dict.items():
            parts = key.split('_')
            current = nested
            
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            current[parts[-1]] = value
        
        return nested

    def _map_args_to_config(self, args_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map command-line argument names to nested configuration structure.

        Args:
            args_dict: Dictionary of command-line arguments

        Returns:
            Nested configuration dictionary
        """
        # Mapping from CLI argument names to config paths
        arg_mapping = {
            # Database options
            'elasticsearch_hosts': ('database', 'elasticsearch', 'hosts'),
            'milvus_host': ('database', 'milvus', 'host'),
            'clickhouse_host': ('database', 'clickhouse', 'host'),
            'hbase_host': ('database', 'hbase', 'host'),
            # Embedding options
            'embedding_model': ('embedding', 'model_name'),
            'embedding_batch_size': ('embedding', 'batch_size'),
            # Processing options
            'chunk_size': ('processing', 'chunk_size'),
            'chunk_overlap': ('processing', 'chunk_overlap'),
            # Logging options
            'log_level': ('logging', 'level'),
            'log_file': ('logging', 'output_file'),
            # Web options
            'web_host': ('web', 'host'),
            'web_port': ('web', 'port'),
        }
        
        nested: Dict[str, Any] = {}
        
        for arg_name, value in args_dict.items():
            if arg_name == 'config':
                # Skip the config file argument
                continue
            
            if arg_name in arg_mapping:
                # Use the mapping to place value in correct nested location
                path = arg_mapping[arg_name]
                current = nested
                
                for part in path[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                
                current[path[-1]] = value
            else:
                # For unmapped arguments, try to infer structure from underscores
                parts = arg_name.split('_')
                current = nested
                
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                
                current[parts[-1]] = value
        
        return nested

    def _create_argument_parser(self) -> argparse.ArgumentParser:
        """
        Create argument parser for common configuration options.

        Returns:
            Configured ArgumentParser
        """
        parser = argparse.ArgumentParser(
            description="RAG Testing System",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        
        # Configuration file
        parser.add_argument(
            '--config',
            type=str,
            help='Path to configuration file (YAML or JSON)'
        )
        
        # Database options
        parser.add_argument(
            '--elasticsearch-hosts',
            type=str,
            nargs='+',
            help='Elasticsearch host URLs'
        )
        parser.add_argument(
            '--milvus-host',
            type=str,
            help='Milvus server host'
        )
        parser.add_argument(
            '--clickhouse-host',
            type=str,
            help='ClickHouse server host'
        )
        parser.add_argument(
            '--hbase-host',
            type=str,
            help='HBase Thrift server host'
        )
        
        # Embedding options
        parser.add_argument(
            '--embedding-model',
            type=str,
            help='Name of the embedding model'
        )
        parser.add_argument(
            '--embedding-batch-size',
            type=int,
            help='Batch size for embedding generation'
        )
        
        # Processing options
        parser.add_argument(
            '--chunk-size',
            type=int,
            help='Maximum size of text chunks in characters'
        )
        parser.add_argument(
            '--chunk-overlap',
            type=int,
            help='Overlap between consecutive chunks'
        )
        
        # Logging options
        parser.add_argument(
            '--log-level',
            type=str,
            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
            help='Logging level'
        )
        parser.add_argument(
            '--log-file',
            type=str,
            help='Path to log file'
        )
        
        # Web API options
        parser.add_argument(
            '--web-host',
            type=str,
            help='Web API server host'
        )
        parser.add_argument(
            '--web-port',
            type=int,
            help='Web API server port'
        )
        
        return parser


def load_config(
    config_file: Optional[str] = None,
    load_env: bool = True,
    load_args: bool = False,
    args: Optional[argparse.Namespace] = None
) -> RAGSystemConfig:
    """
    Convenience function to load configuration from multiple sources.

    Precedence order (highest to lowest):
    1. Command-line arguments
    2. Environment variables
    3. Configuration file
    4. Default values

    Args:
        config_file: Path to configuration file (YAML or JSON)
        load_env: Whether to load from environment variables
        load_args: Whether to load from command-line arguments
        args: Pre-parsed arguments (if load_args is True)

    Returns:
        Validated RAGSystemConfig instance

    Raises:
        ConfigurationError: If configuration is invalid

    Example:
        >>> # Load from file and environment variables
        >>> config = load_config(config_file="config.yaml", load_env=True)
        >>>
        >>> # Load from all sources
        >>> config = load_config(
        ...     config_file="config.yaml",
        ...     load_env=True,
        ...     load_args=True
        ... )
    """
    loader = ConfigLoader()
    
    # Load in order of precedence (lowest to highest)
    if config_file:
        loader.load_from_file(config_file)
    
    if load_env:
        loader.load_from_env()
    
    if load_args:
        loader.load_from_args(args)
    
    return loader.build()
