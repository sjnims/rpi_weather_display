"""Power state controller for the Raspberry Pi weather display.

Manages power states, transitions, and power-related decisions based on
battery status, quiet hours, and system conditions.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import Enum, auto

from rpi_weather_display.constants import (
    ABNORMAL_SLEEP_FACTOR,
    BATTERY_CHARGING_FACTOR,
    BATTERY_CHARGING_MIN,
    BUTTON_PRESS_DELAY,
    CONSERVING_MAX_FACTOR,
    CONSERVING_MIN_FACTOR,
    CONSERVING_SLEEP_MULTIPLIER,
    CRITICAL_SLEEP_FACTOR,
    CRITICAL_SLEEP_MULTIPLIER,
    DEFAULT_MOCK_SLEEP_TIME,
    MAX_BATTERY_PERCENTAGE_SLEEP,
    MAX_SLEEP_MINUTES,
    MIN_SLEEP_MINUTES,
    MINIMUM_MOCK_SLEEP_TIME,
    SECONDS_PER_MINUTE,
    SYSTEM_HALT_DELAY,
    TWELVE_HOURS_IN_MINUTES,
)
from rpi_weather_display.exceptions import CriticalBatteryError, PowerStateError
from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.models.system import BatteryStatus
from rpi_weather_display.utils.battery_monitor import BatteryMonitor
from rpi_weather_display.utils.battery_utils import is_charging
from rpi_weather_display.utils.pijuice_adapter import PiJuiceAction, PiJuiceAdapter, PiJuiceEvent
from rpi_weather_display.utils.time_utils import is_quiet_hours

logger = logging.getLogger(__name__)


class PowerState(Enum):
    """Power state enum for the device."""

    NORMAL = auto()
    CONSERVING = auto()  # Low battery, actively conserving power
    CRITICAL = auto()  # Critical battery, minimal functionality
    CHARGING = auto()  # Connected to power
    QUIET_HOURS = auto()  # During quiet hours


class PowerStateCallback:
    """Wrapper for power state change callbacks."""

    def __init__(self, callback: Callable[[PowerState, PowerState], None]) -> None:
        """Initialize callback wrapper.

        Args:
            callback: Function to call on state change
        """
        self.callback = callback


class PowerStateController:
    """Controls power state management and transitions."""

    def __init__(
        self,
        config: AppConfig,
        battery_monitor: BatteryMonitor,
        pijuice_adapter: PiJuiceAdapter | None = None,
    ) -> None:
        """Initialize power state controller.

        Args:
            config: Application configuration
            battery_monitor: Battery monitoring instance
            pijuice_adapter: Optional PiJuice adapter
        """
        self.config = config
        self.battery_monitor = battery_monitor
        self.pijuice = pijuice_adapter
        self._current_state = PowerState.NORMAL
        self._state_callbacks: list[PowerStateCallback] = []
        self._last_display_refresh: datetime | None = None
        self._last_weather_update: datetime | None = None
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize power state controller.

        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True

        try:
            # Configure PiJuice events if available
            if self.pijuice and self.pijuice.is_initialized():
                self._configure_pijuice_events()

            # Update initial power state
            self._update_power_state()

            self._initialized = True
            logger.info("Power state controller initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize power state controller: {e}")
            self._initialized = False
            return False

    def _configure_pijuice_events(self) -> None:
        """Configure PiJuice events for power management."""
        if not self.pijuice:
            return

        logger.info("Configuring PiJuice events")

        # Configure low charge event
        if self.pijuice.configure_event(
            PiJuiceEvent.LOW_CHARGE, PiJuiceAction.SYSTEM_HALT_POW_OFF, SYSTEM_HALT_DELAY
        ):
            logger.info(f"Configured LOW_CHARGE event with {SYSTEM_HALT_DELAY}s delay")

        # Configure button events
        for button_event in [
            PiJuiceEvent.BUTTON_SW1_PRESS,
            PiJuiceEvent.BUTTON_SW2_PRESS,
            PiJuiceEvent.BUTTON_SW3_PRESS,
        ]:
            if self.pijuice.configure_event(
                button_event, PiJuiceAction.SYSTEM_WAKEUP, BUTTON_PRESS_DELAY
            ):
                logger.info(f"Configured {button_event} for wakeup")

    def get_current_state(self) -> PowerState:
        """Get the current power state.

        Returns:
            Current power state
        """
        return self._current_state

    def update_power_state(self) -> PowerState:
        """Update and return the current power state.

        Returns:
            Updated power state
        """
        self._update_power_state()
        return self._current_state

    def _update_power_state(self) -> None:
        """Update the current power state based on battery and time."""
        old_state = self._current_state
        battery_status = self.battery_monitor.get_battery_status()

        # Determine new state
        new_state = self._determine_power_state(battery_status)

        # Validate state transition
        if new_state != old_state:
            self._validate_state_transition(old_state, new_state, battery_status)
            self._current_state = new_state
            self._notify_state_change(old_state, new_state)

            logger.info(
                f"Power state changed: {old_state.name} -> {new_state.name}",
                extra={
                    "old_state": old_state.name,
                    "new_state": new_state.name,
                    "battery_level": battery_status.level,
                },
            )

    def _determine_power_state(self, battery_status: BatteryStatus) -> PowerState:
        """Determine the appropriate power state.

        Args:
            battery_status: Current battery status

        Returns:
            Appropriate power state
            
        Raises:
            PowerStateError: If state determination results in an invalid state
        """
        # Validate battery status
        if battery_status.level < 0 or battery_status.level > 100:
            raise PowerStateError(
                "Invalid battery level for state determination",
                {
                    "battery_level": battery_status.level,
                    "valid_range": "0-100"
                }
            )
        
        # Charging takes priority
        if is_charging(battery_status):
            return PowerState.CHARGING

        # Check quiet hours
        if is_quiet_hours(self.config.power.quiet_hours_start, self.config.power.quiet_hours_end):
            return PowerState.QUIET_HOURS

        # Check battery levels
        try:
            self.battery_monitor.is_battery_critical()
            # If no exception was raised, battery is not critical
        except CriticalBatteryError:
            # Battery is critical
            return PowerState.CRITICAL
            
        if self.battery_monitor.should_conserve_power():
            return PowerState.CONSERVING

        return PowerState.NORMAL
    
    def _validate_state_transition(
        self, old_state: PowerState, new_state: PowerState, battery_status: BatteryStatus
    ) -> None:
        """Validate that a state transition is allowed.
        
        Args:
            old_state: Current power state
            new_state: Proposed new power state
            battery_status: Current battery status
            
        Raises:
            PowerStateError: If the transition is invalid
        """
        # Define invalid transitions
        invalid_transitions = [
            # Can't go from CRITICAL directly to NORMAL (must go through CONSERVING)
            (PowerState.CRITICAL, PowerState.NORMAL),
            # Can't go from CRITICAL to QUIET_HOURS if battery is still critical
            (PowerState.CRITICAL, PowerState.QUIET_HOURS),
        ]
        
        # Check if this is an invalid transition
        if (old_state, new_state) in invalid_transitions:
            # Special check for CRITICAL -> QUIET_HOURS
            if old_state == PowerState.CRITICAL and new_state == PowerState.QUIET_HOURS:
                # Allow if battery is no longer critical
                if battery_status.level > self.config.power.critical_battery_threshold:
                    return
                    
            raise PowerStateError(
                f"Invalid power state transition: {old_state.name} -> {new_state.name}",
                {
                    "from_state": old_state.name,
                    "to_state": new_state.name,
                    "battery_level": battery_status.level,
                    "reason": "Direct transition not allowed"
                }
            )

    def _notify_state_change(self, old_state: PowerState, new_state: PowerState) -> None:
        """Notify callbacks of state change.

        Args:
            old_state: Previous power state
            new_state: New power state
        """
        for callback_obj in self._state_callbacks:
            try:
                callback_obj.callback(old_state, new_state)
            except Exception as e:
                logger.error(f"Error in power state callback: {e}")

    def register_state_change_callback(
        self, callback: Callable[[PowerState, PowerState], None]
    ) -> PowerStateCallback:
        """Register a callback for power state changes.

        Args:
            callback: Function to call when state changes

        Returns:
            Callback wrapper object
        """
        callback_obj = PowerStateCallback(callback)
        self._state_callbacks.append(callback_obj)
        return callback_obj

    def unregister_state_change_callback(self, callback_obj: PowerStateCallback) -> None:
        """Unregister a power state change callback.

        Args:
            callback_obj: Callback wrapper to remove
        """
        if callback_obj in self._state_callbacks:
            self._state_callbacks.remove(callback_obj)

    def should_refresh_display(self) -> bool:
        """Check if display should be refreshed based on power state.

        Returns:
            True if display should be refreshed, False otherwise
        """
        # Never refresh during quiet hours unless charging
        if self._current_state == PowerState.QUIET_HOURS:
            logger.info("Quiet hours active, skipping display refresh")
            return False

        # Always allow refresh if charging
        if self._current_state == PowerState.CHARGING:
            return True

        # Check minimum interval based on state
        if self._last_display_refresh:
            elapsed = datetime.now() - self._last_display_refresh
            min_interval = self._get_refresh_interval()

            if elapsed < min_interval:
                logger.info(
                    f"Too soon to refresh display: {elapsed} < {min_interval}",
                    extra={"elapsed": str(elapsed), "min_interval": str(min_interval)},
                )
                return False

        return True

    def _get_refresh_interval(self) -> timedelta:
        """Get minimum refresh interval based on power state.

        Returns:
            Minimum time between refreshes
        """
        # Use power state to determine interval
        intervals = {
            PowerState.NORMAL: timedelta(minutes=self.config.display.refresh_interval_minutes),
            PowerState.CONSERVING: timedelta(
                minutes=self.config.display.refresh_interval_minutes * CONSERVING_SLEEP_MULTIPLIER
            ),
            PowerState.CRITICAL: timedelta(
                minutes=self.config.display.refresh_interval_minutes * CRITICAL_SLEEP_MULTIPLIER
            ),
            PowerState.CHARGING: timedelta(minutes=self.config.display.refresh_interval_minutes),
            PowerState.QUIET_HOURS: timedelta(hours=1),  # Shouldn't be called
        }

        return intervals.get(self._current_state, timedelta(minutes=30))

    def should_update_weather(self) -> bool:
        """Check if weather data should be updated based on power state.

        Returns:
            True if weather should be updated, False otherwise
        """
        # Never update during quiet hours
        if self._current_state == PowerState.QUIET_HOURS:
            logger.info("Quiet hours active, skipping weather update")
            return False

        # In critical state, only update if really old
        if self._current_state == PowerState.CRITICAL:
            if self._last_weather_update:
                elapsed = datetime.now() - self._last_weather_update
                if elapsed < timedelta(hours=1):
                    logger.info("Critical power state, skipping frequent weather updates")
                    return False

        return True

    def record_display_refresh(self) -> None:
        """Record that a display refresh occurred."""
        self._last_display_refresh = datetime.now()

    def record_weather_update(self) -> None:
        """Record that a weather update occurred."""
        self._last_weather_update = datetime.now()

    def calculate_sleep_time(self) -> int:
        """Calculate appropriate sleep time based on power state and conditions.

        Returns:
            Sleep time in minutes
        """
        # Development mode uses fixed short sleep
        if self.config.development_mode:
            return max(
                DEFAULT_MOCK_SLEEP_TIME // SECONDS_PER_MINUTE,
                MINIMUM_MOCK_SLEEP_TIME // SECONDS_PER_MINUTE,
            )

        # Update power state first
        self._update_power_state()
        battery_status = self.battery_monitor.get_battery_status()

        # Quiet hours - sleep until they end
        if self._current_state == PowerState.QUIET_HOURS:
            minutes_until_end = self._time_until_quiet_change()
            return min(int(minutes_until_end), TWELVE_HOURS_IN_MINUTES)

        # Get base sleep time from config
        base_sleep = self.config.display.refresh_interval_minutes

        # Apply state-based multipliers
        if self._current_state == PowerState.CRITICAL:
            sleep_minutes = base_sleep * CRITICAL_SLEEP_FACTOR
        elif self._current_state == PowerState.CONSERVING:
            # Scale between min and max based on battery level
            # For battery levels above 25%, use minimum factor
            # For battery levels below 25%, scale linearly to max factor at 0%
            if battery_status.level >= MAX_BATTERY_PERCENTAGE_SLEEP * 100:
                factor = CONSERVING_MIN_FACTOR
            else:
                # Scale from CONSERVING_MIN_FACTOR at 25% to CONSERVING_MAX_FACTOR at 0%
                normalized_level = battery_status.level / (MAX_BATTERY_PERCENTAGE_SLEEP * 100)
                factor = CONSERVING_MIN_FACTOR + (
                    (CONSERVING_MAX_FACTOR - CONSERVING_MIN_FACTOR) * (1 - normalized_level)
                )
            sleep_minutes = base_sleep * factor
        elif self._current_state == PowerState.CHARGING:
            # When charging, update more frequently
            sleep_minutes = max(base_sleep * BATTERY_CHARGING_FACTOR, BATTERY_CHARGING_MIN)
        else:
            # Normal state
            sleep_minutes = base_sleep

        # Check for abnormal discharge rate
        if self.battery_monitor.is_discharge_rate_abnormal():
            logger.warning("Abnormal discharge rate detected, extending sleep time")
            sleep_minutes *= ABNORMAL_SLEEP_FACTOR

        # Apply configured limits
        sleep_minutes = max(MIN_SLEEP_MINUTES, min(sleep_minutes, MAX_SLEEP_MINUTES))

        logger.info(
            f"Calculated sleep time: {sleep_minutes} minutes",
            extra={
                "state": self._current_state.name,
                "battery_level": battery_status.level,
                "base_interval": base_sleep,
            },
        )

        return int(sleep_minutes)

    def _time_until_quiet_change(self) -> float:
        """Calculate minutes until quiet hours start or end.

        Returns:
            Minutes until next quiet hours transition
        """
        now = datetime.now()

        # Parse quiet hours times
        quiet_start = datetime.strptime(self.config.power.quiet_hours_start, "%H:%M").time()
        quiet_end = datetime.strptime(self.config.power.quiet_hours_end, "%H:%M").time()

        # Create datetime objects for today
        today_start = datetime.combine(now.date(), quiet_start)
        today_end = datetime.combine(now.date(), quiet_end)

        # Handle overnight quiet hours
        if quiet_start > quiet_end:
            # Quiet hours span midnight
            if now.time() >= quiet_start:
                # We're in quiet hours, calculate time until tomorrow's end
                end_time = today_end + timedelta(days=1)
            elif now.time() < quiet_end:
                # We're in quiet hours, calculate time until today's end
                end_time = today_end
            else:
                # Not in quiet hours, calculate time until start
                end_time = today_start
        else:
            # Normal quiet hours (don't span midnight)
            if quiet_start <= now.time() < quiet_end:
                # In quiet hours, calculate time until end
                end_time = today_end
            elif now.time() < quiet_start:
                # Before quiet hours, calculate time until start
                end_time = today_start
            else:
                # After quiet hours, calculate time until tomorrow's start
                end_time = today_start + timedelta(days=1)

        # Calculate minutes
        delta = end_time - now
        minutes = delta.total_seconds() / SECONDS_PER_MINUTE

        logger.debug(
            f"Time until quiet hours change: {minutes:.1f} minutes",
            extra={"current_time": now.isoformat(), "target_time": end_time.isoformat()},
        )

        return minutes

    def can_perform_operation(self, operation_type: str, power_cost: float = 1.0) -> bool:
        """Check if an operation should be performed based on power state.

        Args:
            operation_type: Type of operation (e.g., "display_refresh", "weather_update")
            power_cost: Relative power cost of the operation (1.0 = normal)

        Returns:
            True if operation should proceed, False otherwise
        """
        # Always allow in development mode
        if self.config.development_mode:
            return True

        # Update state first
        self._update_power_state()

        # Quiet hours - block most operations
        if self._current_state == PowerState.QUIET_HOURS:
            # Only allow critical operations
            if operation_type in ["shutdown", "low_battery_warning"]:
                return True
            logger.info(f"Blocking {operation_type} during quiet hours")
            return False

        # Critical state - only essential operations
        if self._current_state == PowerState.CRITICAL:
            essential_ops = ["shutdown", "low_battery_warning", "critical_update"]
            if operation_type not in essential_ops:
                logger.info(f"Blocking {operation_type} in critical power state")
                return False

        # Conserving state - limit high-cost operations
        if self._current_state == PowerState.CONSERVING and power_cost > 1.5:
            logger.info(f"Blocking high-cost {operation_type} in conserving state")
            return False

        return True

    def enter_low_power_mode(self) -> None:
        """Enter low power mode by disabling non-essential features."""
        logger.info("Entering low power mode")

        # Force state to at least CONSERVING
        if self._current_state == PowerState.NORMAL:
            old_state = self._current_state
            self._current_state = PowerState.CONSERVING
            self._notify_state_change(old_state, self._current_state)

