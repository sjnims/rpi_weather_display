"""Early error handler for startup failures before logging is configured.

This module provides a simple error handler that can be used during application
startup before the logging system is initialized. It ensures critical errors
are visible to users even if the logging system fails to initialize.
"""

import sys
from datetime import datetime
from typing import Any


def handle_startup_error(
    error_type: str, message: str, details: dict[str, Any] | None = None
) -> None:
    """Handle errors that occur before logging is configured.
    
    This function writes formatted error messages to stderr in a structured way,
    ensuring they are visible even if the logging system is not yet initialized.
    
    Args:
        error_type: Type of error (e.g., "Configuration Error", "Startup Error")
        message: Main error message
        details: Optional dictionary of additional error details
    """
    timestamp = datetime.now().isoformat()
    
    # Write to stderr to ensure visibility
    sys.stderr.write(f"\n[{timestamp}] {error_type}: {message}\n")
    
    if details:
        sys.stderr.write("Details:\n")
        for key, value in details.items():
            sys.stderr.write(f"  {key}: {value}\n")
    
    sys.stderr.flush()


def handle_keyboard_interrupt() -> None:
    """Handle keyboard interrupt gracefully."""
    sys.stderr.write("\n\nShutdown requested by user (Ctrl+C)\n")
    sys.stderr.flush()


def handle_unexpected_error(error: Exception) -> None:
    """Handle unexpected errors during startup.
    
    Args:
        error: The unexpected exception
    """
    timestamp = datetime.now().isoformat()
    sys.stderr.write(f"\n[{timestamp}] Unexpected Error: {type(error).__name__}: {error}\n")
    sys.stderr.write("This is likely a bug. Please report it with the full error details.\n")
    sys.stderr.flush()