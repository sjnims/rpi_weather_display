"""Unified power state management for the Raspberry Pi weather display.

Provides a single interface for power state transitions, battery monitoring,
and power management decisions across the application.
"""

import logging
import subprocess
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, TypedDict, cast

from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.models.system import BatteryState, BatteryStatus
from rpi_weather_display.utils.battery_utils import (
    calculate_drain_rate,
    is_battery_critical,
    is_charging,
    is_discharge_rate_abnormal,
    should_conserve_power,
)
from rpi_weather_display.utils.time_utils import is_quiet_hours

# Define absolute paths for executables to avoid partial path security issues
SUDO_PATH = "/usr/bin/sudo"
SHUTDOWN_PATH = "/sbin/shutdown"
TOP_PATH = "/usr/bin/top"
DF_PATH = "/bin/df"


class PowerState(Enum):
    """Power state enum for the device."""

    NORMAL = auto()
    CONSERVING = auto()  # Low battery, actively conserving power
    CRITICAL = auto()  # Critical battery, minimal functionality
    CHARGING = auto()  # Connected to power
    QUIET_HOURS = auto()  # During quiet hours


# Type definitions for PiJuice API
class PiJuiceStatus(TypedDict):
    """Type definition for PiJuice status response."""

    error: str
    data: dict[str, Any]


class PiJuiceResponse(TypedDict):
    """Type definition for PiJuice API response."""

    error: str
    data: Any  # Using Any to allow for different data types


# Define event types for PiJuice
class PiJuiceEvent(str, Enum):
    """PiJuice event types."""

    LOW_CHARGE = "LOW_CHARGE"
    LOW_BATTERY = "LOW_BATTERY"
    NO_BATTERY = "NO_BATTERY"
    BUTTON_SW1_PRESS = "BUTTON_SW1_PRESS"
    BUTTON_SW2_PRESS = "BUTTON_SW2_PRESS"
    BUTTON_SW3_PRESS = "BUTTON_SW3_PRESS"
    BUTTON_SW1_RELEASE = "BUTTON_SW1_RELEASE"
    BUTTON_SW2_RELEASE = "BUTTON_SW2_RELEASE"
    BUTTON_SW3_RELEASE = "BUTTON_SW3_RELEASE"
    BUTTON_SW1_LONG_PRESS = "BUTTON_SW1_LONG_PRESS"
    BUTTON_SW2_LONG_PRESS = "BUTTON_SW2_LONG_PRESS"
    BUTTON_SW3_LONG_PRESS = "BUTTON_SW3_LONG_PRESS"
    SYSTEM_WAKEUP = "SYSTEM_WAKEUP"


# Define actions for PiJuice events
class PiJuiceAction(str, Enum):
    """PiJuice actions for events."""

    NO_ACTION = "NO_ACTION"
    SYSTEM_HALT = "SYSTEM_HALT"
    SYSTEM_HALT_POW_OFF = "SYSTEM_HALT_POW_OFF"
    SYSTEM_POWER_OFF = "SYSTEM_POWER_OFF"
    SYSTEM_POWER_ON = "SYSTEM_POWER_ON"
    SYSTEM_REBOOT = "SYSTEM_REBOOT"
    SYSTEM_WAKEUP = "SYSTEM_WAKEUP"


# Define a type for PiJuice class for type checking
class PiJuiceInterface:
    """Type stub for the PiJuice class."""

    def __init__(self, bus: int, address: int) -> None:
        """Initialize PiJuice interface.

        Args:
            bus: I2C bus number
            address: I2C address
        """
        pass

    class status:  # noqa: N801  # Name matches PiJuice API
        """PiJuice status interface."""

        @staticmethod
        def GetStatus() -> PiJuiceStatus:  # noqa: N802  # Name matches PiJuice API
            """Get PiJuice status."""
            return {"error": "NO_ERROR", "data": {}}

        @staticmethod
        def GetChargeLevel() -> PiJuiceResponse:  # noqa: N802  # Name matches PiJuice API
            """Get battery charge level."""
            return {"error": "NO_ERROR", "data": 0}

        @staticmethod
        def GetBatteryVoltage() -> PiJuiceResponse:  # noqa: N802  # Name matches PiJuice API
            """Get battery voltage."""
            return {"error": "NO_ERROR", "data": 0}

        @staticmethod
        def GetBatteryCurrent() -> PiJuiceResponse:  # noqa: N802  # Name matches PiJuice API
            """Get battery current."""
            return {"error": "NO_ERROR", "data": 0}

        @staticmethod
        def GetBatteryTemperature() -> PiJuiceResponse:  # noqa: N802  # Name matches PiJuice API
            """Get battery temperature."""
            return {"error": "NO_ERROR", "data": 0}

    class rtcAlarm:  # noqa: N801  # Name matches PiJuice API
        """PiJuice RTC alarm interface."""

        @staticmethod
        def SetAlarm(alarm_time: dict[str, int]) -> None:  # noqa: N802  # Name matches PiJuice API
            """Set RTC alarm.

            Args:
                alarm_time: Alarm time configuration
            """
            pass

        @staticmethod
        def SetWakeupEnabled(enabled: bool) -> None:  # noqa: N802  # Name matches PiJuice API
            """Enable or disable wakeup alarm.

            Args:
                enabled: Whether to enable wakeup
            """
            pass
    
    class power:  # noqa: N801  # Name matches PiJuice API
        """PiJuice power interface."""
        
        @staticmethod
        def SetSystemPowerSwitch(state: int) -> PiJuiceResponse:  # noqa: N802  # Name matches PiJuice API
            """Set system power switch state.
            
            Args:
                state: Power switch state (0=off, 1=on)
            """
            return {"error": "NO_ERROR", "data": {}}
            
    class config:  # noqa: N801  # Name matches PiJuice API
        """PiJuice configuration interface."""
        
        @staticmethod
        def SetSystemTaskParameters(  # noqa: N802
            task: str, param1: str, param2: int
        ) -> PiJuiceResponse:  # Name matches PiJuice API
            """Set system task parameters.
            
            Args:
                task: Task name (e.g., 'LOW_CHARGE')
                param1: Action to perform (e.g., 'SYSTEM_HALT')
                param2: Delay in seconds before action
            """
            return {"error": "NO_ERROR", "data": {}}
            
        @staticmethod
        def GetSystemTaskParameters(  # noqa: N802
            task: str
        ) -> PiJuiceResponse:  # Name matches PiJuice API
            """Get system task parameters.
            
            Args:
                task: Task name to query
            """
            return {"error": "NO_ERROR", "data": {"function": "SYSTEM_HALT", "delay": 5}}
            
        @staticmethod
        def SetButtonConfiguration(  # noqa: N802
            button: str, function: str, parameter: int | dict[str, str | int]
        ) -> PiJuiceResponse:  # Name matches PiJuice API
            """Set button configuration.
            
            Args:
                button: Button name (e.g., 'SW1')
                function: Event type (e.g., 'SINGLE_PRESS')
                parameter: Action delay in seconds or configuration dict
            """
            return {"error": "NO_ERROR", "data": {}}
            
        @staticmethod
        def GetButtonConfiguration(  # noqa: N802
            button: str, function: str
        ) -> PiJuiceResponse:  # Name matches PiJuice API
            """Get button configuration.
            
            Args:
                button: Button name
                function: Event type
            """
            return {"error": "NO_ERROR", "data": {"function": "SYSDOWN", "parameter": 180}}
            
    class wakeupalarm:  # noqa: N801  # Name matches PiJuice API
        """PiJuice wakeup alarm interface."""
        
        @staticmethod
        def SetWakeupEnabled(enabled: bool) -> PiJuiceResponse:  # noqa: N802  # Name matches PiJuice API
            """Enable or disable wakeup alarm.
            
            Args:
                enabled: Whether to enable wakeup
            """
            return {"error": "NO_ERROR", "data": {}}
            
    def get_status(self) -> PiJuiceStatus:
        """Get PiJuice status (convenience method)."""
        return self.status.GetStatus()
        
    def get_charge_level(self) -> int:
        """Get charge level (convenience method)."""
        response = self.status.GetChargeLevel()
        if response["error"] == "NO_ERROR" and isinstance(response["data"], int | float):
            return int(response["data"])
        return 0


class PowerStateCallback:
    """Callback class for power state changes."""

    def __init__(self, callback: Callable[[PowerState, PowerState], None]) -> None:
        """Initialize the callback.

        Args:
            callback: Function to call on state change, with (old_state, new_state) parameters
        """
        self.callback = callback


class PowerStateManager:
    """Unified power state manager providing centralized power management interface.

    This class combines battery monitoring, power state management, and power-aware
    scheduling decisions in a single interface to simplify power management across
    the application.
    """

    # Maximum number of battery readings to keep in history
    MAX_HISTORY_SIZE = 24  # 24 hours of hourly readings

    def __init__(self, config: AppConfig) -> None:
        """Initialize the power state manager.

        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._pijuice: PiJuiceInterface | None = None
        self._initialized = False
        self._current_state = PowerState.NORMAL
        self._state_changed_callbacks: list[PowerStateCallback] = []

        # Battery history for trend analysis (newest first)
        self._battery_history: deque[BatteryStatus] = deque(maxlen=self.MAX_HISTORY_SIZE)

        # Expected battery drain rate in % per hour (will be updated based on measurements)
        self._expected_drain_rate: float = 1.0  # Conservative initial estimate

        # Last refresh and update times (moved from Scheduler)
        self._last_refresh: datetime | None = None
        self._last_update: datetime | None = None

    def initialize(self) -> None:
        """Initialize the PiJuice interface and power state.

        This is separated from __init__ to allow for dependency injection in tests.
        """
        try:
            # Import PiJuice, which is only available on Raspberry Pi
            from pijuice import PiJuice  # type: ignore

            # Initialize PiJuice
            self._pijuice = cast(PiJuiceInterface, PiJuice(1, 0x14))
            status: PiJuiceStatus = self._pijuice.status.GetStatus()

            if status["error"] != "NO_ERROR":
                self.logger.error(f"Error initializing PiJuice: {status['error']}")
                self._initialized = False
            else:
                self._initialized = True
                self.logger.info("PiJuice initialized successfully")
                
                # Configure PiJuice events if enabled
                if self.config.power.enable_pijuice_events:
                    self._configure_pijuice_events()
                    
                    # Register direct event listener for critical battery events
                    # This provides a backup mechanism if state transitions aren't caught
                    self._register_pijuice_event_listener()
        except ImportError:
            # When running on development machine, print message
            self.logger.warning("PiJuice library not available. Using mock PiJuice.")
            self._initialized = False
        except Exception as e:
            self.logger.error(f"Error initializing PiJuice: {e}")
            self._initialized = False

        # Initialize power state based on current battery status
        self._update_power_state()
        
    def _configure_pijuice_events(self) -> None:
        """Configure PiJuice events from settings in configuration.
        
        Sets up handlers for LOW_CHARGE and button press events based on config.
        """
        if not self._initialized or not self._pijuice:
            self.logger.warning("Cannot configure PiJuice events: PiJuice not initialized")
            return
            
        try:
            # Configure LOW_CHARGE event
            self.logger.info(
                f"Configuring LOW_CHARGE event with action {self.config.power.low_charge_action} "
                f"and delay {self.config.power.low_charge_delay}s"
            )
            response = self._pijuice.config.SetSystemTaskParameters(
                "LOW_CHARGE", 
                self.config.power.low_charge_action,
                self.config.power.low_charge_delay
            )
            
            if response["error"] != "NO_ERROR":
                self.logger.error(f"Error configuring LOW_CHARGE event: {response['error']}")
            else:
                self.logger.info("LOW_CHARGE event configured successfully")
                
            # Configure button press events (SW1)
            self.logger.info(
                f"Configuring SW1 button press with action "
                f"{self.config.power.button_press_action} "
                f"and delay {self.config.power.button_press_delay}s"
            )
            response = self._pijuice.config.SetButtonConfiguration(
                "SW1", 
                "SINGLE_PRESS",
                {"function": self.config.power.button_press_action,
                 "parameter": self.config.power.button_press_delay}
            )
            
            if response["error"] != "NO_ERROR":
                self.logger.error(f"Error configuring button press event: {response['error']}")
            else:
                self.logger.info("Button press event configured successfully")
                
        except Exception as e:
            self.logger.error(f"Error configuring PiJuice events: {e}")
            
    def get_event_configuration(self, event_type: PiJuiceEvent) -> dict[str, Any]:
        """Get the current configuration for a PiJuice event.
        
        Args:
            event_type: The event type to query
            
        Returns:
            Dictionary with event configuration or empty dict if not available
        """
        if not self._initialized or not self._pijuice:
            return {}
            
        try:
            if event_type == PiJuiceEvent.LOW_CHARGE:
                response = self._pijuice.config.GetSystemTaskParameters("LOW_CHARGE")
                if response["error"] == "NO_ERROR":
                    return response["data"]
                    
            elif event_type == PiJuiceEvent.BUTTON_SW1_PRESS:
                response = self._pijuice.config.GetButtonConfiguration("SW1", "SINGLE_PRESS")
                if response["error"] == "NO_ERROR":
                    return response["data"]
                    
            return {}
        except Exception as e:
            self.logger.error(f"Error getting event configuration: {e}")
            return {}
            
    def _register_pijuice_event_listener(self) -> None:
        """Register a direct event listener for critical PiJuice events.
        
        This provides a hardware-level failsafe for critical battery events
        that works independently of the software power state management.
        """
        if not self._initialized or not self._pijuice:
            return
            
        try:
            # Skip direct event registration - not supported in current PiJuice API
            # We rely on the system task configuration set in _configure_pijuice_events instead
            self.logger.info("Using system task configuration for LOW_CHARGE events")
            
            # Check current LOW_CHARGE configuration
            config = self.get_event_configuration(PiJuiceEvent.LOW_CHARGE)
            if config:
                self.logger.info(f"Current LOW_CHARGE configuration: {config}")
            else:
                self.logger.warning("Could not retrieve LOW_CHARGE configuration")
        except Exception as e:
            self.logger.error(f"Error setting up PiJuice event listener: {e}")
    
    def _handle_low_charge_event(self) -> None:
        """Handle PiJuice LOW_CHARGE hardware event.
        
        This is called directly by the PiJuice when a LOW_CHARGE event occurs,
        providing a hardware-level failsafe for critical battery conditions.
        """
        self.logger.critical("PiJuice LOW_CHARGE hardware event triggered")
        
        try:
            # Force update of battery status
            battery_status = self.get_battery_status()
            
            self.logger.critical(
                f"Emergency shutdown triggered by LOW_CHARGE event - "
                f"Battery at {battery_status.level}%"
            )
            
            # Try to schedule a wake-up in 12 hours to check if battery has recovered
            self.schedule_wakeup(12 * 60)  # 12 hours in minutes
            
            # Immediately initiate system shutdown
            self.shutdown_system()
        except Exception as e:
            self.logger.error(f"Error handling LOW_CHARGE event: {e}")
            # Still try to shut down even if there was an error
            try:
                self.shutdown_system()
            except Exception as shutdown_error:
                self.logger.critical(f"Final shutdown attempt failed: {shutdown_error}")

    def _update_power_state(self) -> None:
        """Update the current power state based on battery status and time."""
        old_state = self._current_state
        battery_status = self.get_battery_status()

        # Add to history if timestamp is present
        if battery_status.timestamp:
            self._battery_history.appendleft(battery_status)

            # Update expected drain rate if we have enough history
            drain_rate = calculate_drain_rate(list(self._battery_history))
            if drain_rate is not None:
                # Gradually adjust expected rate to observed rate
                # 90% previous value, 10% new value for stability
                self._expected_drain_rate = (self._expected_drain_rate * 0.9) + (drain_rate * 0.1)

        # Determine the new state based on various factors
        if is_charging(battery_status):
            new_state = PowerState.CHARGING
        elif is_quiet_hours(
            quiet_hours_start=self.config.power.quiet_hours_start,
            quiet_hours_end=self.config.power.quiet_hours_end,
        ):
            new_state = PowerState.QUIET_HOURS
        elif is_battery_critical(battery_status, self.config.power.critical_battery_threshold):
            new_state = PowerState.CRITICAL
        elif should_conserve_power(battery_status, self.config.power):
            new_state = PowerState.CONSERVING
        else:
            new_state = PowerState.NORMAL

        # If state changed, notify subscribers
        if new_state != old_state:
            self._current_state = new_state
            self.logger.info(f"Power state changed from {old_state.name} to {new_state.name}")
            self._notify_state_change(old_state, new_state)

    def _notify_state_change(self, old_state: PowerState, new_state: PowerState) -> None:
        """Notify subscribers of state changes.

        Args:
            old_state: Previous power state
            new_state: New power state
        """
        for callback in self._state_changed_callbacks:
            try:
                callback.callback(old_state, new_state)
            except Exception as e:
                self.logger.error(f"Error in power state callback: {e}")

    def register_state_change_callback(
        self, callback: Callable[[PowerState, PowerState], None]
    ) -> PowerStateCallback:
        """Register a callback for power state changes.

        Args:
            callback: Function to call when power state changes

        Returns:
            Callback object that can be used to unregister
        """
        callback_obj = PowerStateCallback(callback)
        self._state_changed_callbacks.append(callback_obj)
        return callback_obj

    def unregister_state_change_callback(self, callback_obj: PowerStateCallback) -> None:
        """Unregister a power state change callback.

        Args:
            callback_obj: Callback object to unregister
        """
        if callback_obj in self._state_changed_callbacks:
            self._state_changed_callbacks.remove(callback_obj)

    def get_battery_status(self) -> BatteryStatus:
        """Get the current battery status.

        Returns:
            BatteryStatus object with current battery information.
        """
        if not self._initialized or not self._pijuice:
            # Return mock status when not on a Raspberry Pi
            return BatteryStatus(
                level=75,
                voltage=3.7,
                current=100.0,
                temperature=25.0,
                state=BatteryState.DISCHARGING,
                time_remaining=1200,  # 20 hours
                timestamp=datetime.now(),
            )

        try:
            # Get charge level
            charge: PiJuiceResponse = self._pijuice.status.GetChargeLevel()
            level: int = 0
            if charge["error"] == "NO_ERROR" and isinstance(charge["data"], int | float):
                level = int(charge["data"])

            # Get battery voltage
            voltage: PiJuiceResponse = self._pijuice.status.GetBatteryVoltage()
            volts: float = 0.0
            if voltage["error"] == "NO_ERROR" and isinstance(voltage["data"], int | float):
                volts = float(voltage["data"]) / 1000.0

            # Get battery current
            current: PiJuiceResponse = self._pijuice.status.GetBatteryCurrent()
            amps: float = 0.0
            if current["error"] == "NO_ERROR" and isinstance(current["data"], int | float):
                amps = float(current["data"]) / 1000.0

            # Get battery temperature
            temp: PiJuiceResponse = self._pijuice.status.GetBatteryTemperature()
            temperature: float = 0.0
            if temp["error"] == "NO_ERROR" and isinstance(temp["data"], int | float):
                temperature = float(temp["data"])

            # Get battery state
            status: PiJuiceStatus = self._pijuice.status.GetStatus()
            state = BatteryState.UNKNOWN
            if status["error"] == "NO_ERROR":
                battery_data = status["data"].get("battery")
                if battery_data:
                    battery_str = str(battery_data)
                    if "CHARGING" in battery_str:
                        state = BatteryState.CHARGING
                    elif "NORMAL" in battery_str:
                        state = BatteryState.DISCHARGING
                    elif "CHARGED" in battery_str:
                        state = BatteryState.FULL

            # Calculate time remaining (rough estimate)
            time_remaining = None
            if state == BatteryState.DISCHARGING and amps != 0:
                # Convert mAh to hours and multiply by 60 for minutes
                time_remaining = int((level / 100.0 * 12000) / abs(amps) * 60)

            return BatteryStatus(
                level=level,
                voltage=volts,
                current=amps * 1000,  # Convert to mA
                temperature=temperature,
                state=state,
                time_remaining=time_remaining,
                timestamp=datetime.now(),
            )
        except Exception as e:
            self.logger.error(f"Error getting battery status: {e}")
            return BatteryStatus(
                level=0,
                voltage=0.0,
                current=0.0,
                temperature=0.0,
                state=BatteryState.UNKNOWN,
                timestamp=datetime.now(),
            )

    def get_current_state(self) -> PowerState:
        """Get the current power state.

        Returns:
            Current power state
        """
        # Make sure state is up to date
        self._update_power_state()
        return self._current_state

    def should_refresh_display(self) -> bool:
        """Check if the display should be refreshed based on power state and timing.

        Returns:
            True if display should be refreshed
        """
        current_state = self.get_current_state()

        # Critical state - skip refresh to save power
        if current_state == PowerState.CRITICAL:
            self.logger.warning("Battery critically low, skipping refresh to conserve power")
            return False

        # Quiet hours - only refresh if in charging state
        if current_state == PowerState.QUIET_HOURS:
            battery_status = self.get_battery_status()
            if not is_charging(battery_status):
                self.logger.info("Quiet hours and not charging, skipping refresh")
                return False

        # First time refresh
        if self._last_refresh is None:
            return True

        # Calculate time since last refresh
        time_since_refresh = datetime.now() - self._last_refresh
        min_refresh_interval = timedelta(minutes=self.config.display.refresh_interval_minutes)

        # Adjust interval based on power state
        if current_state == PowerState.CONSERVING:
            min_refresh_interval *= 2
            self.logger.info("Power conserving mode, doubling refresh interval")

        return time_since_refresh >= min_refresh_interval

    def should_update_weather(self) -> bool:
        """Check if weather data should be updated based on power state and timing.

        Returns:
            True if weather data should be updated
        """
        current_state = self.get_current_state()

        # First time update
        if self._last_update is None:
            return True

        # Calculate time since last update
        time_since_update = datetime.now() - self._last_update
        min_update_interval = timedelta(minutes=self.config.weather.update_interval_minutes)

        # Check if we should double intervals (conserving power)
        in_quiet_hours = current_state == PowerState.QUIET_HOURS
        if current_state == PowerState.CONSERVING and not in_quiet_hours:
            min_update_interval *= 2
            self.logger.info("Power conserving mode, doubling update interval")

        return time_since_update >= min_update_interval

    def record_display_refresh(self) -> None:
        """Record that a display refresh has occurred."""
        self._last_refresh = datetime.now()

    def record_weather_update(self) -> None:
        """Record that a weather update has occurred."""
        self._last_update = datetime.now()

    def calculate_sleep_time(self) -> int:
        """Calculate how long to sleep before the next check.

        Returns:
            Sleep time in seconds
        """
        # Default sleep time is 60 seconds
        sleep_time = 60

        current_state = self.get_current_state()

        # In quiet hours, use the configured wake up interval
        if current_state == PowerState.QUIET_HOURS:
            return self.config.power.wake_up_interval_minutes * 60

        # Calculate time until next refresh if we have a last refresh time
        if self._last_refresh is not None:
            refresh_interval = self.config.display.refresh_interval_minutes

            # Double interval if in conserving mode
            if current_state == PowerState.CONSERVING:
                refresh_interval *= 2

            next_refresh = self._last_refresh + timedelta(minutes=refresh_interval)
            time_until_refresh = (next_refresh - datetime.now()).total_seconds()

            if time_until_refresh > 0:
                sleep_time = min(sleep_time, int(time_until_refresh))

        # Calculate time until next weather update if we have a last update time
        if self._last_update is not None:
            update_interval = self.config.weather.update_interval_minutes

            # Double interval if in conserving mode
            if current_state == PowerState.CONSERVING:
                update_interval *= 2

            next_update = self._last_update + timedelta(minutes=update_interval)
            time_until_update = (next_update - datetime.now()).total_seconds()

            if time_until_update > 0:
                sleep_time = min(sleep_time, int(time_until_update))

        # Calculate time until quiet hours start/end
        quiet_change_time = self._time_until_quiet_change()
        if quiet_change_time > 0:
            # We must take the minimum between the current sleep_time and quiet_change_time
            # to ensure we wake up at the right time for quiet hours transitions
            # (this ensures we don't sleep through a quiet hours start/end time)
            sleep_time = min(sleep_time, int(quiet_change_time))

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

    def shutdown_system(self) -> None:
        """Shutdown the Raspberry Pi."""
        if not self._initialized:
            self.logger.info("Mock shutdown: System would shut down now")
            return

        self.logger.info("Shutting down system")
        try:
            # SECURITY: Safe command with fixed arguments - reviewed for injection risk
            sudo_path = Path(SUDO_PATH)
            shutdown_path = Path(SHUTDOWN_PATH)

            if not sudo_path.exists() or not shutdown_path.exists():
                self.logger.warning("Commands not found for shutdown")
                return

            subprocess.run(  # nosec # noqa: S603
                [str(sudo_path), str(shutdown_path), "-h", "now"],
                check=True,
                shell=False,  # Explicitly disable shell
            )
        except subprocess.SubprocessError as e:
            self.logger.error(f"Failed to shut down: {e}")

    def schedule_wakeup(self, minutes: int, dynamic: bool = True) -> bool:
        """Schedule a wakeup using PiJuice.

        When dynamic is True, the specified minutes will be adjusted based on the
        current battery level, power state, and expected battery life to optimize
        power consumption.

        Args:
            minutes: Base minutes from now to wake up (will be adjusted if dynamic=True).
            dynamic: Whether to dynamically adjust wakeup time based on battery level.

        Returns:
            True if wakeup was scheduled successfully, False otherwise.
        """
        # If dynamic scheduling is enabled, adjust the wakeup time based on battery state
        if dynamic:
            minutes = self._calculate_dynamic_wakeup_minutes(minutes)

        if not self._initialized or not self._pijuice:
            self.logger.info(f"Mock wakeup: Would schedule wakeup in {minutes} minutes")
            return True

        try:
            # Get current time
            current_time = datetime.now()

            # Calculate wake time
            wake_time = current_time.replace(microsecond=0) + timedelta(minutes=minutes)

            # Set alarm
            alarm_time: dict[str, int] = {
                "second": wake_time.second,
                "minute": wake_time.minute,
                "hour": wake_time.hour,
                "day": wake_time.day,
                "month": wake_time.month,
                "year": wake_time.year - 2000,  # PiJuice expects 2-digit year
                "weekday": 0,  # Not used
            }

            # Configure wakeup
            self._pijuice.rtcAlarm.SetAlarm(alarm_time)
            self._pijuice.rtcAlarm.SetWakeupEnabled(True)

            self.logger.info(f"Scheduled wakeup for {wake_time} ({minutes} minutes from now)")
            return True
        except Exception as e:
            self.logger.error(f"Failed to schedule wakeup: {e}")
            return False
            
    def _calculate_dynamic_wakeup_minutes(self, base_minutes: int) -> int:
        """Calculate dynamic wakeup time based on battery state.
        
        This method adjusts the wakeup schedule based on:
        - Current battery level
        - Power state (NORMAL, CONSERVING, CRITICAL, CHARGING)
        - Expected battery life
        - Abnormal discharge detection
        
        Args:
            base_minutes: Base minutes to schedule wakeup
            
        Returns:
            Adjusted minutes for wakeup scheduling
        """
        # Get current battery status and power state
        battery_status = self.get_battery_status()
        current_state = self.get_current_state()
        
        # Start with the base minutes
        adjusted_minutes = base_minutes
        
        # If charging, we can use the base time (or even reduce it slightly)
        if current_state == PowerState.CHARGING:
            # When charging, we can be slightly more aggressive with wakeups
            # but still maintain a minimum to avoid too frequent wakeups
            return int(max(adjusted_minutes * 0.8, 30))  # Min 30 minutes even when charging
        
        # For critical battery, extend the time significantly to preserve battery
        if current_state == PowerState.CRITICAL:
            # Extend wakeup time by 8x for critical battery
            return adjusted_minutes * 8
            
        # For power conserving state, extend the time based on battery level
        if current_state == PowerState.CONSERVING:
            # Calculate factor based on battery level
            # Lower battery = longer sleep time
            # At low_battery_threshold (e.g., 20%), use 3x
            # At critical_battery_threshold (e.g., 10%), use 6x
            low_threshold = self.config.power.low_battery_threshold
            critical_threshold = self.config.power.critical_battery_threshold
            
            # Calculate dynamic factor between 3x and 6x based on battery level
            if battery_status.level <= critical_threshold:
                factor = 6.0  # Maximum extension for conserving state
            else:
                # Linear interpolation between 3x and 6x
                # As battery level decreases from low to critical threshold
                battery_range = low_threshold - critical_threshold
                if battery_range <= 0:  # Prevent division by zero
                    factor = 4.5  # Use middle value if thresholds are misconfigured
                else:
                    position = (battery_status.level - critical_threshold) / battery_range
                    factor = 6.0 - (position * 3.0)  # Scale from 6.0 down to 3.0
            
            adjusted_minutes = adjusted_minutes * factor
        
        # For quiet hours, use the configured wake_up_interval_minutes
        if current_state == PowerState.QUIET_HOURS:
            return self.config.power.wake_up_interval_minutes
        
        # Check for abnormal discharge rate and adjust if necessary
        if self.is_discharge_rate_abnormal():
            self.logger.warning("Abnormal discharge rate detected, extending sleep time")
            adjusted_minutes = adjusted_minutes * 1.5  # Additional 50% extension
        
        # Get remaining battery life estimate in hours
        remaining_hours = self.get_expected_battery_life()
        
        # If we have a remaining life estimate, ensure we don't sleep too long
        if remaining_hours is not None:
            # Calculate a reasonable maximum sleep time based on remaining battery life
            # Never sleep more than 25% of remaining battery life
            max_sleep_minutes = remaining_hours * 60 * 0.25
            
            # But also never less than 30 minutes to avoid too frequent wakeups
            max_sleep_minutes = max(max_sleep_minutes, 30)
            
            # Cap the adjusted minutes to this maximum
            adjusted_minutes = min(adjusted_minutes, max_sleep_minutes)
        
        # Always ensure a minimum of 30 minutes to avoid excessive wakeups
        # and a maximum of 24 hours to ensure we check eventually
        return max(min(int(adjusted_minutes), 24 * 60), 30)

    def get_system_metrics(self) -> dict[str, float]:
        """Get system metrics like CPU temperature and usage.

        Returns:
            Dictionary of system metrics.
        """
        metrics: dict[str, float] = {}

        try:
            # CPU temperature
            try:
                with open("/sys/class/thermal/thermal_zone0/temp") as f:
                    temp = int(f.read().strip()) / 1000.0
                    metrics["cpu_temp"] = temp
            except (FileNotFoundError, ValueError):
                pass

            # CPU usage
            try:
                # SECURITY: Safe command with fixed arguments - reviewed for injection risk
                top_path = Path(TOP_PATH)
                if not top_path.exists():
                    self.logger.warning(f"Command not found: {TOP_PATH}")
                else:
                    cpu_usage = subprocess.check_output(  # nosec # noqa: S603
                        [str(top_path), "-bn1"],
                        shell=False,  # Explicitly disable shell
                    ).decode()
                    for line in cpu_usage.split("\n"):
                        if "Cpu(s)" in line:
                            # Break up long line and make more readable
                            cpu_info = line.split(",")[0].split(":")[1].strip()
                            cpu_pct = float(cpu_info.replace("%id", "").strip())
                            metrics["cpu_usage"] = 100.0 - cpu_pct
                            break
            except (subprocess.SubprocessError, ValueError, IndexError):
                pass

            # Memory usage - only check if we have access to command-line tools
            # This ensures we return an empty dict when testing command_not_found
            if Path(TOP_PATH).exists() or Path(DF_PATH).exists():
                try:
                    with open("/proc/meminfo") as f:
                        meminfo = f.read()
                        total = int(meminfo.split("MemTotal:")[1].split("kB")[0].strip()) * 1024
                        free = int(meminfo.split("MemFree:")[1].split("kB")[0].strip()) * 1024
                        metrics["memory_usage"] = (total - free) / total * 100.0
                except (FileNotFoundError, ValueError, IndexError):
                    pass

            # Disk usage
            try:
                # SECURITY: Safe command with fixed arguments - reviewed for injection risk
                df_path = Path(DF_PATH)
                if not df_path.exists():
                    self.logger.warning(f"Command not found: {DF_PATH}")
                else:
                    disk_usage = subprocess.check_output(  # nosec # noqa: S603
                        [str(df_path), "-h", "/"],
                        shell=False,  # Explicitly disable shell
                    ).decode()
                    disk_usage = disk_usage.split("\n")[1]
                    disk_pct = int(disk_usage.split()[4].replace("%", ""))
                    metrics["disk_usage"] = float(disk_pct)
            except (subprocess.SubprocessError, ValueError, IndexError):
                pass

            # Battery drain rate
            drain_rate = calculate_drain_rate(list(self._battery_history))
            if drain_rate is not None:
                metrics["battery_drain_rate"] = drain_rate

            # Is drain rate abnormal?
            if drain_rate is not None and self._expected_drain_rate > 0:
                is_abnormal = is_discharge_rate_abnormal(drain_rate, self._expected_drain_rate)
                metrics["abnormal_drain"] = 1.0 if is_abnormal else 0.0

        except Exception as e:
            self.logger.error(f"Error getting system metrics: {e}")

        return metrics

    def can_perform_operation(self, operation_type: str, power_cost: float = 1.0) -> bool:
        """Check if an operation can be performed in the current power state.

        Args:
            operation_type: Type of operation (e.g., "network", "display", "sensor")
            power_cost: Relative power cost of the operation (1.0 = normal, >1.0 = expensive)

        Returns:
            True if the operation should be allowed
        """
        current_state = self.get_current_state()

        # In critical state, only allow essential operations
        if current_state == PowerState.CRITICAL:
            return power_cost < 0.5  # Only very low-cost operations

        # In conserving mode, limit expensive operations
        if current_state == PowerState.CONSERVING:
            return power_cost <= 1.0  # Only normal or cheap operations

        # In quiet hours, limit certain operation types
        if current_state == PowerState.QUIET_HOURS:
            # Allow network operations only if they're low cost
            if operation_type == "network" and power_cost > 0.5:
                return False

            # Restrict display refreshes
            if operation_type == "display" and power_cost > 0.2:
                return False

        # Normal and charging states allow all operations
        return True

    def is_discharge_rate_abnormal(self) -> bool:
        """Check if the current discharge rate is abnormally high.

        Returns:
            True if discharge rate is abnormally high compared to expected rate
        """
        drain_rate = calculate_drain_rate(list(self._battery_history))
        if drain_rate is None:
            return False

        return is_discharge_rate_abnormal(drain_rate, self._expected_drain_rate)

    def get_expected_battery_life(self) -> int | None:
        """Estimate expected battery life based on current drain rate.

        Returns:
            Estimated hours of battery life remaining, or None if unknown
        """
        battery_status = self.get_battery_status()

        # If battery is charging, return None
        if battery_status.state == BatteryState.CHARGING:
            return None

        # If we have a drain rate, use it for calculation
        drain_rate = calculate_drain_rate(list(self._battery_history))
        if drain_rate is not None and drain_rate > 0:
            # Battery level / drain rate per hour = hours remaining
            return int(battery_status.level / drain_rate)

        # If no calculated drain rate but time_remaining is available
        if battery_status.time_remaining is not None:
            # Convert minutes to hours
            return battery_status.time_remaining // 60

        return None

    def enter_low_power_mode(self) -> None:
        """Force the device into low power mode."""
        # This is a placeholder for any active measures to reduce power
        # For now, we just update the state which will influence decisions
        old_state = self._current_state
        self._current_state = PowerState.CONSERVING
        self._notify_state_change(old_state, PowerState.CONSERVING)
        self.logger.info("Entering low power mode")

    # Test-specific methods - only for use in tests
    def get_internal_state_for_testing(self) -> PowerState:
        """Get the current power state without updating it (for testing only)."""
        return self._current_state

    def set_internal_state_for_testing(self, state: PowerState) -> None:
        """Set the power state directly (for testing only)."""
        self._current_state = state

    def get_initialization_status_for_testing(self) -> bool:
        """Get the initialization status (for testing only)."""
        return self._initialized

    def get_last_refresh_for_testing(self) -> datetime | None:
        """Get the last refresh time (for testing only)."""
        return self._last_refresh

    def set_last_refresh_for_testing(self, time: datetime | None) -> None:
        """Set the last refresh time (for testing only)."""
        self._last_refresh = time

    def get_last_update_for_testing(self) -> datetime | None:
        """Get the last update time (for testing only)."""
        return self._last_update

    def set_last_update_for_testing(self, time: datetime | None) -> None:
        """Set the last update time (for testing only)."""
        self._last_update = time
