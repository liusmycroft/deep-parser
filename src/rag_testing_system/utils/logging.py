"""Structured logging utilities with JSON formatter."""

import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path
from pythonjsonlogger import jsonlogger

from ..config.models import LoggingConfig, LogLevel


class StructuredLogger:
    """
    Structured logger with JSON formatting and context management.
    
    Provides consistent logging across the RAG Testing System with:
    - JSON formatted logs for machine parsing
    - Contextual information (component, correlation ID)
    - Multiple output targets (console, file)
    - Configurable log levels
    """

    def __init__(
        self,
        name: str,
        config: LoggingConfig,
        component: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Initialize structured logger.

        Args:
            name: Logger name (typically module name)
            config: Logging configuration
            component: Component name for context
            correlation_id: Correlation ID for request tracing
        """
        self.logger = logging.getLogger(name)
        self.component = component or name
        self.correlation_id = correlation_id
        self._config = config
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Set log level
        self.logger.setLevel(self._get_log_level(config.level))
        
        # Prevent propagation to root logger
        self.logger.propagate = False
        
        # Add handlers based on configuration
        if config.enable_console:
            self._add_console_handler(config)
        
        if config.output_file:
            self._add_file_handler(config)

    def _get_log_level(self, level: LogLevel) -> int:
        """Convert LogLevel enum to logging level constant."""
        level_map = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
        }
        return level_map[level]

    def _add_console_handler(self, config: LoggingConfig) -> None:
        """Add console handler with appropriate formatter."""
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(self._get_log_level(config.level))
        
        if config.format == "json":
            formatter = self._create_json_formatter()
        else:
            formatter = self._create_text_formatter()
        
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def _add_file_handler(self, config: LoggingConfig) -> None:
        """Add file handler with appropriate formatter."""
        # Create log directory if it doesn't exist
        log_path = Path(config.output_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        handler = logging.FileHandler(config.output_file)
        handler.setLevel(self._get_log_level(config.level))
        
        if config.format == "json":
            formatter = self._create_json_formatter()
        else:
            formatter = self._create_text_formatter()
        
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def _create_json_formatter(self) -> jsonlogger.JsonFormatter:
        """Create JSON formatter with standard fields."""
        return jsonlogger.JsonFormatter(
            fmt='%(timestamp)s %(level)s %(component)s %(message)s',
            rename_fields={
                'levelname': 'level',
                'name': 'logger_name'
            }
        )

    def _create_text_formatter(self) -> logging.Formatter:
        """Create text formatter for human-readable logs."""
        return logging.Formatter(
            fmt='%(asctime)s - %(levelname)s - %(component)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def _add_context(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Add contextual information to log record.

        Args:
            extra: Additional fields to include

        Returns:
            Dictionary with context fields
        """
        context = {
            'component': self.component,
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        if self.correlation_id:
            context['correlation_id'] = self.correlation_id
        
        if extra:
            context.update(extra)
        
        return context

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message with context."""
        extra = self._add_context(kwargs)
        self.logger.debug(message, extra=extra)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message with context."""
        extra = self._add_context(kwargs)
        self.logger.info(message, extra=extra)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message with context."""
        extra = self._add_context(kwargs)
        self.logger.warning(message, extra=extra)

    def error(
        self,
        message: str,
        error: Optional[Exception] = None,
        **kwargs: Any
    ) -> None:
        """
        Log error message with context and optional exception details.

        Args:
            message: Error message
            error: Exception object (if available)
            **kwargs: Additional context fields
        """
        extra = self._add_context(kwargs)
        
        if error:
            extra['error_type'] = type(error).__name__
            extra['error_message'] = str(error)
        
        self.logger.error(message, extra=extra, exc_info=error is not None)

    def with_context(
        self,
        component: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> "StructuredLogger":
        """
        Create a new logger with updated context.

        Args:
            component: New component name
            correlation_id: New correlation ID

        Returns:
            New StructuredLogger instance with updated context
        """
        return StructuredLogger(
            name=self.logger.name,
            config=self._config,
            component=component or self.component,
            correlation_id=correlation_id or self.correlation_id
        )


class LoggerFactory:
    """Factory for creating structured loggers with consistent configuration."""

    _config: Optional[LoggingConfig] = None

    @classmethod
    def configure(cls, config: LoggingConfig) -> None:
        """
        Configure the logger factory with logging settings.

        Args:
            config: Logging configuration
        """
        cls._config = config

    @classmethod
    def get_logger(
        cls,
        name: str,
        component: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> StructuredLogger:
        """
        Get a structured logger instance.

        Args:
            name: Logger name (typically __name__)
            component: Component name for context
            correlation_id: Correlation ID for request tracing

        Returns:
            StructuredLogger instance

        Raises:
            RuntimeError: If factory not configured
        """
        if cls._config is None:
            # Use default configuration if not configured
            from ..config.models import LoggingConfig
            cls._config = LoggingConfig()
        
        return StructuredLogger(
            name=name,
            config=cls._config,
            component=component,
            correlation_id=correlation_id
        )


def setup_logging(config: LoggingConfig) -> None:
    """
    Set up logging for the entire application.

    Args:
        config: Logging configuration
    """
    LoggerFactory.configure(config)


def get_logger(
    name: str,
    component: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> StructuredLogger:
    """
    Convenience function to get a logger.

    Args:
        name: Logger name (typically __name__)
        component: Component name for context
        correlation_id: Correlation ID for request tracing

    Returns:
        StructuredLogger instance
    """
    return LoggerFactory.get_logger(name, component, correlation_id)
