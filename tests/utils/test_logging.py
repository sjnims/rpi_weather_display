"""Tests for the logging module.

Tests cover the setup_logging function, including configuration of log levels,
formatters, and handlers with various output formats.
"""

# ruff: noqa: B017, S101
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from unittest.mock import patch

import pytest
from structlog.stdlib import ProcessorFormatter

from rpi_weather_display.models.config import LoggingConfig
from rpi_weather_display.utils.logging import setup_logging


@pytest.fixture()
def basic_config() -> LoggingConfig:
    """Create a basic logging configuration with no file output."""
    return LoggingConfig(
        level="INFO",
        file=None,
        format="json",
        max_size_mb=5,
        backup_count=3,
    )


@pytest.fixture()
def json_file_config(tmp_path: Path) -> LoggingConfig:
    """Create a logging configuration with JSON file output."""
    log_file = tmp_path / "logs" / "test.log"
    return LoggingConfig(
        level="DEBUG",
        file=str(log_file),
        format="json",
        max_size_mb=5,
        backup_count=3,
    )


@pytest.fixture()
def text_file_config(tmp_path: Path) -> LoggingConfig:
    """Create a logging configuration with text file output."""
    log_file = tmp_path / "logs" / "test.log"
    return LoggingConfig(
        level="DEBUG",
        file=str(log_file),
        format="text",  # Not "json", so it will use ConsoleRenderer
        max_size_mb=5,
        backup_count=3,
    )


def test_setup_logging_basic(basic_config: LoggingConfig) -> None:
    """Test basic logger setup with no file output."""
    logger = setup_logging(basic_config, "test_logger")

    # Verify logger configuration
    assert logger.name == "test_logger"
    assert logger.level == logging.INFO

    # Verify handlers
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.StreamHandler)
    assert logger.handlers[0].stream == sys.stdout


def test_setup_logging_json_format(basic_config: LoggingConfig) -> None:
    """Test logger setup with JSON formatter."""
    # Set format to json
    basic_config.format = "json"

    with patch("structlog.processors.JSONRenderer") as mock_json_renderer:
        # Simply verify the JSONRenderer is created
        logger = setup_logging(basic_config, "test_logger")

        # Verify JSONRenderer was used
        assert mock_json_renderer.call_count == 1

        # Verify handler has a formatter
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, ProcessorFormatter)


def test_setup_logging_console_format(basic_config: LoggingConfig) -> None:
    """Test logger setup with console text formatter."""
    # Set format to text (not json)
    basic_config.format = "text"

    with patch("structlog.dev.ConsoleRenderer") as mock_console_renderer:
        # Simply verify the ConsoleRenderer is created
        logger = setup_logging(basic_config, "test_logger")

        # Verify ConsoleRenderer was used
        assert mock_console_renderer.call_count == 1

        # Verify handler has a formatter
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, ProcessorFormatter)


def test_setup_logging_with_file(json_file_config: LoggingConfig) -> None:
    """Test logger setup with file output."""
    logger = setup_logging(json_file_config, "test_logger")

    # Verify logger has two handlers (console and file)
    assert len(logger.handlers) == 2
    assert isinstance(logger.handlers[0], logging.StreamHandler)
    assert isinstance(logger.handlers[1], RotatingFileHandler)

    # Verify file handler configuration
    file_handler = logger.handlers[1]
    # RotatingFileHandler has baseFilename as a string, but we created it from Path
    assert file_handler.baseFilename == str(json_file_config.file)
    assert file_handler.maxBytes == json_file_config.max_size_mb * 1024 * 1024
    assert file_handler.backupCount == json_file_config.backup_count

    # Verify log directory was created
    # Ensure file is not None for type checking
    file_path = json_file_config.file
    assert file_path is not None, "file_path should not be None in this test"
    log_dir = Path(file_path).parent
    assert log_dir.exists()


def test_setup_logging_with_text_format_file(text_file_config: LoggingConfig) -> None:
    """Test logger setup with text format and file output."""
    with patch("structlog.dev.ConsoleRenderer") as mock_console_renderer:
        # Simply verify the ConsoleRenderer is created and used for formatting
        logger = setup_logging(text_file_config, "test_logger")

        # Verify ConsoleRenderer was used
        assert mock_console_renderer.call_count == 1

        # Verify both handlers have formatters of the right type
        console_handler = logger.handlers[0]
        file_handler = logger.handlers[1]
        assert isinstance(console_handler.formatter, ProcessorFormatter)
        assert isinstance(file_handler.formatter, ProcessorFormatter)

        # Verify handlers are of the right type
        assert isinstance(console_handler, logging.StreamHandler)
        assert isinstance(file_handler, RotatingFileHandler)


def test_setup_logging_file_error(json_file_config: LoggingConfig) -> None:
    """Test error handling when setting up file logging."""
    # Make the Path.mkdir method raise an exception
    with patch("pathlib.Path.mkdir", side_effect=PermissionError("Permission denied")):
        # Also patch the logger.error method to verify it's called
        with patch("logging.Logger.error") as mock_error:
            logger = setup_logging(json_file_config, "test_logger")

            # Verify only one handler (console) was added
            assert len(logger.handlers) == 1
            assert isinstance(logger.handlers[0], logging.StreamHandler)

            # Verify error was logged
            assert mock_error.call_count == 1
            error_msg = mock_error.call_args[0][0]
            assert "Failed to set up file logging" in error_msg
            assert "Permission denied" in error_msg


def test_setup_logging_custom_level(basic_config: LoggingConfig) -> None:
    """Test logger setup with custom log level."""
    # Test with DEBUG level
    basic_config.level = "DEBUG"
    logger = setup_logging(basic_config, "test_logger")
    assert logger.level == logging.DEBUG

    # Test with ERROR level
    basic_config.level = "ERROR"
    logger = setup_logging(basic_config, "test_logger")
    assert logger.level == logging.ERROR

    # Test with invalid level (should default to INFO)
    basic_config.level = "INVALID_LEVEL"
    logger = setup_logging(basic_config, "test_logger")
    assert logger.level == logging.INFO


def test_structlog_configuration(basic_config: LoggingConfig) -> None:
    """Test structlog configuration."""
    with patch("structlog.configure") as mock_configure:
        setup_logging(basic_config, "test_logger")

        # Verify structlog.configure was called
        assert mock_configure.call_count == 1

        # Verify processors and other parameters
        _, kwargs = mock_configure.call_args
        assert "processors" in kwargs
        assert len(kwargs["processors"]) == 9  # Verify all processors are included
        assert kwargs["context_class"] is dict
        assert kwargs["cache_logger_on_first_use"] is True
