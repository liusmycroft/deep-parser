"""Tests for structured logging."""

import json
import logging
from pathlib import Path
import pytest

from rag_testing_system.config.models import LoggingConfig, LogLevel
from rag_testing_system.utils.logging import (
    StructuredLogger,
    LoggerFactory,
    setup_logging,
    get_logger,
)


class TestStructuredLogger:
    """Test structured logging functionality."""

    def test_logger_creation(self):
        """Test that logger can be created with configuration."""
        config = LoggingConfig(
            level=LogLevel.INFO,
            format="json",
            enable_console=False
        )
        
        logger = StructuredLogger("test_logger", config)
        
        assert logger.logger.name == "test_logger"
        assert logger.component == "test_logger"

    def test_logger_with_custom_component(self):
        """Test logger with custom component name."""
        config = LoggingConfig(
            level=LogLevel.INFO,
            format="json",
            enable_console=False
        )
        
        logger = StructuredLogger("test_logger", config, component="CustomComponent")
        
        assert logger.component == "CustomComponent"

    def test_logger_with_correlation_id(self):
        """Test logger with correlation ID."""
        config = LoggingConfig(
            level=LogLevel.INFO,
            format="json",
            enable_console=False
        )
        
        logger = StructuredLogger(
            "test_logger",
            config,
            correlation_id="test-correlation-123"
        )
        
        assert logger.correlation_id == "test-correlation-123"

    def test_log_level_filtering(self):
        """Test that log level filtering works correctly."""
        config = LoggingConfig(
            level=LogLevel.WARNING,
            format="json",
            enable_console=False
        )
        
        logger = StructuredLogger("test_logger", config)
        
        # Logger should be set to WARNING level
        assert logger.logger.level == logging.WARNING

    def test_with_context(self):
        """Test creating logger with updated context."""
        config = LoggingConfig(
            level=LogLevel.INFO,
            format="json",
            enable_console=False
        )
        
        logger1 = StructuredLogger("test_logger", config, component="Component1")
        logger2 = logger1.with_context(component="Component2", correlation_id="new-id")
        
        assert logger1.component == "Component1"
        assert logger2.component == "Component2"
        assert logger2.correlation_id == "new-id"

    def test_file_logging(self, tmp_path):
        """Test logging to file."""
        log_file = tmp_path / "test.log"
        
        config = LoggingConfig(
            level=LogLevel.INFO,
            format="text",
            enable_console=False,
            output_file=str(log_file)
        )
        
        logger = StructuredLogger("test_logger", config)
        logger.info("Test message")
        
        # Verify log file was created and contains message
        assert log_file.exists()
        content = log_file.read_text()
        assert "Test message" in content


class TestLoggerFactory:
    """Test logger factory functionality."""

    def test_factory_configuration(self):
        """Test configuring the logger factory."""
        config = LoggingConfig(
            level=LogLevel.DEBUG,
            format="json"
        )
        
        LoggerFactory.configure(config)
        
        assert LoggerFactory._config == config

    def test_get_logger_from_factory(self):
        """Test getting logger from factory."""
        config = LoggingConfig(
            level=LogLevel.INFO,
            format="json",
            enable_console=False
        )
        
        LoggerFactory.configure(config)
        logger = LoggerFactory.get_logger("test_logger")
        
        assert isinstance(logger, StructuredLogger)
        assert logger.logger.name == "test_logger"

    def test_get_logger_with_default_config(self):
        """Test getting logger without prior configuration."""
        # Reset factory config
        LoggerFactory._config = None
        
        # Should use default config
        logger = LoggerFactory.get_logger("test_logger")
        
        assert isinstance(logger, StructuredLogger)

    def test_setup_logging_function(self):
        """Test setup_logging convenience function."""
        config = LoggingConfig(
            level=LogLevel.WARNING,
            format="json",
            enable_console=False
        )
        
        setup_logging(config)
        
        assert LoggerFactory._config == config

    def test_get_logger_convenience_function(self):
        """Test get_logger convenience function."""
        config = LoggingConfig(
            level=LogLevel.INFO,
            format="json",
            enable_console=False
        )
        
        setup_logging(config)
        logger = get_logger("test_logger", component="TestComponent")
        
        assert isinstance(logger, StructuredLogger)
        assert logger.component == "TestComponent"


class TestLogLevels:
    """Test different log levels."""

    def test_debug_level(self):
        """Test DEBUG log level."""
        config = LoggingConfig(
            level=LogLevel.DEBUG,
            format="json",
            enable_console=False
        )
        
        logger = StructuredLogger("test_logger", config)
        assert logger.logger.level == logging.DEBUG

    def test_info_level(self):
        """Test INFO log level."""
        config = LoggingConfig(
            level=LogLevel.INFO,
            format="json",
            enable_console=False
        )
        
        logger = StructuredLogger("test_logger", config)
        assert logger.logger.level == logging.INFO

    def test_warning_level(self):
        """Test WARNING log level."""
        config = LoggingConfig(
            level=LogLevel.WARNING,
            format="json",
            enable_console=False
        )
        
        logger = StructuredLogger("test_logger", config)
        assert logger.logger.level == logging.WARNING

    def test_error_level(self):
        """Test ERROR log level."""
        config = LoggingConfig(
            level=LogLevel.ERROR,
            format="json",
            enable_console=False
        )
        
        logger = StructuredLogger("test_logger", config)
        assert logger.logger.level == logging.ERROR
