"""Scheduler module for managing the display and power states.

Handles timing of display refreshes, weather updates, and sleep cycles based on
battery status, quiet hours, and configured intervals to optimize power usage.
"""

import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta

from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.models.system import BatteryStatus
from rpi_weather_display.utils import (
    is_battery_critical,
    is_battery_low,
    is_charging,
    is_quiet_hours,
    should_double_intervals,
)


class Scheduler:
    """Scheduler for managing display refreshes and sleep cycles."""

    def __init__(self, config: AppConfig) -> None:
        """Initialize the scheduler.

        Args:
            config: Application configuration.
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._last_refresh: datetime | None = None
        self._last_update: datetime | None = None
        self._running = False

    def should_refresh(self, battery_status: BatteryStatus) -> bool:
        """Check if the display should be refreshed.

        Args:
            battery_status: Current battery status.

        Returns:
            True if the display should be refreshed, False otherwise.
        """
        # Don't refresh if this is during quiet hours and battery is not charging
        if (
            is_quiet_hours(
                quiet_hours_start=self.config.power.quiet_hours_start,
                quiet_hours_end=self.config.power.quiet_hours_end,
            )
            and not is_charging(battery_status)
            and not self.config.debug
        ):
            self.logger.info("Quiet hours and not charging, skipping refresh")
            return False

        # Check if battery is too low
        if is_battery_critical(battery_status, self.config.power.critical_battery_threshold):
            self.logger.warning("Battery critically low, skipping refresh to conserve power")
            return False

        # Check if it's time for a refresh
        if self._last_refresh is None:
            return True

        time_since_refresh = datetime.now() - self._last_refresh
        min_refresh_interval = timedelta(minutes=self.config.display.refresh_interval_minutes)

        # If battery is low, double the refresh interval unless charging
        if is_battery_low(battery_status, self.config.power.low_battery_threshold):
            min_refresh_interval *= 2
            self.logger.info("Battery low, doubling refresh interval")

        return time_since_refresh >= min_refresh_interval

    def should_update(self, battery_status: BatteryStatus) -> bool:
        """Check if weather data should be updated.

        Args:
            battery_status: Current battery status.

        Returns:
            True if weather data should be updated, False otherwise.
        """
        # Always update if we haven't updated yet
        if self._last_update is None:
            return True

        time_since_update = datetime.now() - self._last_update
        min_update_interval = timedelta(minutes=self.config.weather.update_interval_minutes)

        # If battery is low, double the update interval unless charging
        in_quiet_hours = is_quiet_hours(
            quiet_hours_start=self.config.power.quiet_hours_start,
            quiet_hours_end=self.config.power.quiet_hours_end,
        )

        if should_double_intervals(battery_status, self.config.power, in_quiet_hours):
            min_update_interval *= 2
            self.logger.info("Battery low, doubling update interval")

        return time_since_update >= min_update_interval

    def run(
        self,
        refresh_callback: Callable[[], None],
        update_callback: Callable[[], None],
        battery_callback: Callable[[], BatteryStatus],
        sleep_callback: Callable[[int], bool],
    ) -> None:
        """Run the scheduler main loop.

        Args:
            refresh_callback: Function to call when display should be refreshed.
            update_callback: Function to call when weather data should be updated.
            battery_callback: Function to get battery status.
            sleep_callback: Function to call to put system to sleep.
        """
        self._running = True

        try:
            while self._running:
                # Get current battery status
                battery_status = battery_callback()

                # Check if we should update weather data
                if self.should_update(battery_status):
                    self.logger.info("Updating weather data")
                    update_callback()
                    self._last_update = datetime.now()

                # Check if we should refresh the display
                if self.should_refresh(battery_status):
                    self.logger.info("Refreshing display")
                    refresh_callback()
                    self._last_refresh = datetime.now()

                # Determine how long to sleep
                sleep_time = self._calculate_sleep_time(battery_status)

                # If we're going to sleep for a long time, use deep sleep
                if sleep_time > 5 * 60:  # More than 5 minutes
                    self.logger.info(f"Entering deep sleep for {sleep_time // 60} minutes")
                    # Convert seconds to minutes for the sleep callback
                    if sleep_callback(sleep_time // 60):
                        # If sleep_callback returns True, it means the system will wake up
                        # automatically
                        # So we can break out of the loop
                        break
                    # If sleep_callback returns False, it means we should continue running
                    # Use a short sleep to avoid busy-waiting
                    time.sleep(10)
                else:
                    # Short sleep
                    self.logger.info(f"Sleeping for {sleep_time} seconds")
                    time.sleep(sleep_time)
        except KeyboardInterrupt:
            self.logger.info("Scheduler interrupted by user")
            self._running = False
        except Exception as e:
            self.logger.error(f"Error in scheduler: {e}")
            self._running = False

    def _calculate_sleep_time(self, battery_status: BatteryStatus) -> int:
        """Calculate how long to sleep before the next check.

        Args:
            battery_status: Current battery status.

        Returns:
            Sleep time in seconds.
        """
        # Default sleep time is 60 seconds
        sleep_time = 60

        # If in quiet hours, sleep for the wake_up_interval
        if is_quiet_hours(
            quiet_hours_start=self.config.power.quiet_hours_start,
            quiet_hours_end=self.config.power.quiet_hours_end,
        ):
            return self.config.power.wake_up_interval_minutes * 60

        # Not in quiet hours, calculate based on refresh/update times
        # Calculate time until next refresh
        if self._last_refresh is not None:
            refresh_interval = self.config.display.refresh_interval_minutes

            # If battery is low, double the refresh interval unless charging
            if is_battery_low(battery_status, self.config.power.low_battery_threshold):
                refresh_interval *= 2

            next_refresh = self._last_refresh + timedelta(minutes=refresh_interval)
            time_until_refresh = (next_refresh - datetime.now()).total_seconds()

            if time_until_refresh > 0:
                sleep_time = min(sleep_time, int(time_until_refresh))

        # Calculate time until next update
        if self._last_update is not None:
            update_interval = self.config.weather.update_interval_minutes

            # If battery is low, double the update interval unless charging
            if is_battery_low(battery_status, self.config.power.low_battery_threshold):
                update_interval *= 2

            next_update = self._last_update + timedelta(minutes=update_interval)
            time_until_update = (next_update - datetime.now()).total_seconds()

            if time_until_update > 0:
                sleep_time = min(sleep_time, int(time_until_update))

        # Calculate time until quiet hours start/end
        time_until_quiet_change = self._time_until_quiet_change()
        if time_until_quiet_change > 0:
            sleep_time = min(sleep_time, int(time_until_quiet_change))

        # Ensure we don't sleep for too short a time (min 10 seconds)
        return max(sleep_time, 10)

    def _time_until_quiet_change(self) -> float:
        """Calculate time until quiet hours start or end.

        Returns:
            Time in seconds until quiet hours start or end, or -1 if error.
        """
        try:
            start_hour, start_minute = map(int, self.config.power.quiet_hours_start.split(":"))
            end_hour, end_minute = map(int, self.config.power.quiet_hours_end.split(":"))

            from datetime import time as dt_time

            start_time = dt_time(start_hour, start_minute)
            end_time = dt_time(end_hour, end_minute)

            now = datetime.now()
            today = now.date()
            tomorrow = today + timedelta(days=1)

            # Convert time objects to datetime
            start_dt = datetime.combine(today, start_time)
            end_dt = datetime.combine(today, end_time)

            # If end time is before start time, it means it's on the next day
            if end_time < start_time:
                end_dt = datetime.combine(tomorrow, end_time)

            # Calculate time until start and end
            time_until_start = (start_dt - now).total_seconds()
            time_until_end = (end_dt - now).total_seconds()

            # Adjust if both are negative
            if time_until_start < 0 and time_until_end < 0:
                # Both times are in the past, so we need to look at the next day
                start_dt = datetime.combine(tomorrow, start_time)
                end_dt = datetime.combine(tomorrow, end_time)

                # If end time is before start time, it means it's on the next day
                if end_time < start_time:
                    end_dt = datetime.combine(tomorrow + timedelta(days=1), end_time)

                time_until_start = (start_dt - now).total_seconds()
                time_until_end = (end_dt - now).total_seconds()

            # Return the nearest time
            if time_until_start >= 0 and time_until_end >= 0:
                return min(time_until_start, time_until_end)
            elif time_until_start >= 0:
                return time_until_start
            elif time_until_end >= 0:
                return time_until_end
            else:
                return -1
        except ValueError:
            self.logger.error(
                f"Invalid quiet hours format: "
                f"{self.config.power.quiet_hours_start} - {self.config.power.quiet_hours_end}"
            )
            return -1
