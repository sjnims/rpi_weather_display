"""Time-related utility functions for the Raspberry Pi weather display.

Provides common time and date utilities used across client and server components.
"""

import logging
from datetime import datetime
from datetime import time as dt_time


def is_quiet_hours(quiet_hours_start: str, quiet_hours_end: str) -> bool:
    """Check if current time is within quiet hours.

    Args:
        quiet_hours_start: Quiet hours start time in format "HH:MM".
        quiet_hours_end: Quiet hours end time in format "HH:MM".

    Returns:
        True if current time is within quiet hours, False otherwise.
    """
    logger = logging.getLogger(__name__)

    # Parse quiet hours from config
    try:
        start_hour, start_minute = map(int, quiet_hours_start.split(":"))
        end_hour, end_minute = map(int, quiet_hours_end.split(":"))

        start_time = dt_time(start_hour, start_minute)
        end_time = dt_time(end_hour, end_minute)

        # Get current time
        now = datetime.now().time()

        # Check if current time is within quiet hours
        if start_time <= end_time:
            # Simple case: start time is before end time
            return start_time <= now <= end_time
        else:
            # Complex case: quiet hours span midnight
            return now >= start_time or now <= end_time
    except ValueError:
        logger.error(f"Invalid quiet hours format: {quiet_hours_start} - {quiet_hours_end}")
        return False
