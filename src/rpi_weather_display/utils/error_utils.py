"""Utility functions for error handling and reporting.

Provides functions for extracting information from exceptions and
enhancing error messages with file and line information.
"""

import sys
import traceback


def get_error_location() -> str:
    """Extract the file name and line number from the current exception.

    Returns:
        String containing filename and line number of the exception.
    """
    _, _, exc_traceback = sys.exc_info()
    if exc_traceback:
        tb = traceback.extract_tb(exc_traceback)
        if tb:
            frame = tb[-1]  # Get the last frame in the traceback (closest to the error)
            return f"{frame.filename}:{frame.lineno}"
    return "unknown:0"
