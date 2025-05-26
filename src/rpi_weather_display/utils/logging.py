"""Logging configuration module for the weather display application.

Provides structured logging setup with support for console and file output
in both JSON and human-readable formats.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler

import structlog
from structlog.stdlib import ProcessorFormatter

from rpi_weather_display.constants import BYTES_PER_MEGABYTE
from rpi_weather_display.models.config import LoggingConfig
from rpi_weather_display.utils.early_error_handler import handle_startup_error
from rpi_weather_display.utils.path_utils import path_resolver


def setup_logging(config: LoggingConfig, name: str) -> logging.Logger:
    """Set up logging with the specified configuration.

    Args:
        config: Logging configuration.
        name: Logger name.

    Returns:
        Configured logger instance.
    """
    # Create logger
    logger = logging.getLogger(name)

    # Clear existing handlers
    logger.handlers = []

    # Set log level
    level = getattr(logging, config.level.upper(), logging.INFO)
    logger.setLevel(level)

    # Configure structlog renderer based on format
    renderer = (
        structlog.processors.JSONRenderer()
        if config.format.lower() == "json"
        else structlog.dev.ConsoleRenderer()
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            renderer,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        cache_logger_on_first_use=True,
    )

    # Configure the root structlog logger
    # We call get_logger but don't need to use the returned logger directly
    # as the configuration above applies globally
    _ = structlog.get_logger(name)

    # Create formatter using the configured renderer
    formatter = ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
        ],
    )

    # Choose where to send logs based on configuration
    if config.file:
        try:
            # Ensure directory exists
            from rpi_weather_display.utils import file_utils

            log_path = path_resolver.normalize_path(config.file)
            file_utils.ensure_dir_exists(log_path.parent)

            # Create file handler
            file_handler = RotatingFileHandler(
                config.file,
                maxBytes=config.max_size_mb * BYTES_PER_MEGABYTE,
                backupCount=config.backup_count,
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(level)
            logger.addHandler(file_handler)
        except Exception as e:
            error_msg = f"Failed to set up file logging: {e}"
            handle_startup_error("LOGGING_FILE_ERROR", error_msg, {"log_file": str(config.file)})

            # Fall back to console logging if file logging fails
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(level)
            logger.addHandler(console_handler)

            # Log the error through the logger
            logger.error(error_msg)
    else:
        # Add console handler when no file is configured
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)

    return logger
