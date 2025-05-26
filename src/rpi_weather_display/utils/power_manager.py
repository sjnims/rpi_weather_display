"""Unified power state management for the Raspberry Pi weather display.

Provides a single interface for power state transitions, battery monitoring,
and power management decisions across the application.
"""

import logging
import subprocess
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from rpi_weather_display.utils.power_state_controller import PowerStateCallback

from rpi_weather_display.exceptions import WakeupSchedulingError
from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.models.system import BatteryStatus
from rpi_weather_display.utils.battery_monitor import BatteryMonitor
from rpi_weather_display.utils.pijuice_adapter import PiJuiceAdapter
from rpi_weather_display.utils.power_state_controller import PowerState, PowerStateController
from rpi_weather_display.utils.system_metrics_collector import SystemMetricsCollector

logger = logging.getLogger(__name__)


class PowerStateManager:
    """Unified power state manager providing centralized power management interface.

    This class combines battery monitoring, power state management, and power-aware
    scheduling decisions in a single interface to simplify power management across
    the application.
    """

    def __init__(self, config: AppConfig) -> None:
        """Initialize the power state manager.

        Args:
            config: Application configuration
        """
        self.config = config
        self._pijuice_adapter: PiJuiceAdapter | None = None
        self._battery_monitor: BatteryMonitor | None = None
        self._power_controller: PowerStateController | None = None
        self._metrics_collector = SystemMetricsCollector()
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the power state manager and its components."""
        if self._initialized:
            return

        # Initialize PiJuice adapter
        if not self.config.development_mode:
            self._pijuice_adapter = PiJuiceAdapter()
            if not self._pijuice_adapter.initialize():
                logger.warning("PiJuice initialization failed, continuing without hardware")
                self._pijuice_adapter = None

        # Initialize battery monitor
        self._battery_monitor = BatteryMonitor(self.config, self._pijuice_adapter)

        # Initialize power state controller
        self._power_controller = PowerStateController(
            self.config, self._battery_monitor, self._pijuice_adapter
        )
        self._power_controller.initialize()

        self._initialized = True
        logger.info("Power state manager initialized")

    # Battery monitoring delegation
    def get_battery_status(self) -> BatteryStatus:
        """Get comprehensive battery status information.

        Returns:
            Battery status with charge level, state, voltage, current, and health metrics
        """
        if not self._battery_monitor:
            raise RuntimeError("Power state manager not initialized")
        return self._battery_monitor.get_battery_status()

    def get_expected_battery_life(self) -> int | None:
        """Calculate expected battery life in hours based on current drain rate.

        Returns:
            Expected hours of battery life, or None if cannot be calculated
        """
        if not self._battery_monitor:
            return None
        return self._battery_monitor.get_expected_battery_life()

    def is_discharge_rate_abnormal(self) -> bool:
        """Check if the current battery discharge rate is abnormal.

        Returns:
            True if discharge rate is abnormal, False otherwise
        """
        if not self._battery_monitor:
            return False
        return self._battery_monitor.is_discharge_rate_abnormal()

    # Power state control delegation
    def get_current_state(self) -> PowerState:
        """Get the current power state.

        Returns:
            Current power state
        """
        if not self._power_controller:
            return PowerState.NORMAL
        return self._power_controller.get_current_state()

    def should_refresh_display(self) -> bool:
        """Check if display should be refreshed based on power state.

        Returns:
            True if display should be refreshed, False otherwise
        """
        if not self._power_controller:
            return True
        return self._power_controller.should_refresh_display()

    def should_update_weather(self) -> bool:
        """Check if weather data should be updated based on power state.

        Returns:
            True if weather should be updated, False otherwise
        """
        if not self._power_controller:
            return True
        return self._power_controller.should_update_weather()

    def record_display_refresh(self) -> None:
        """Record that a display refresh occurred."""
        if self._power_controller:
            self._power_controller.record_display_refresh()

    def record_weather_update(self) -> None:
        """Record that a weather update occurred."""
        if self._power_controller:
            self._power_controller.record_weather_update()

    def calculate_sleep_time(self) -> int:
        """Calculate appropriate sleep time based on power state and conditions.

        Returns:
            Sleep time in minutes
        """
        if not self._power_controller:
            return 30  # Default
        return self._power_controller.calculate_sleep_time()

    def can_perform_operation(self, operation_type: str, power_cost: float = 1.0) -> bool:
        """Check if an operation should be performed based on power state.

        Args:
            operation_type: Type of operation (e.g., "display_refresh", "weather_update")
            power_cost: Relative power cost of the operation (1.0 = normal)

        Returns:
            True if operation should proceed, False otherwise
        """
        if not self._power_controller:
            return True
        return self._power_controller.can_perform_operation(operation_type, power_cost)

    def enter_low_power_mode(self) -> None:
        """Enter low power mode by disabling non-essential features."""
        if self._power_controller:
            self._power_controller.enter_low_power_mode()

    # System operations
    def shutdown_system(self) -> None:
        """Shutdown the Raspberry Pi."""
        if self.config.development_mode:
            logger.info("Development mode: System would shut down now")
            return

        logger.info("Shutting down system")
        try:
            # Security: Using hardcoded paths and arguments to prevent injection
            subprocess.run(  # noqa: S603
                ["/usr/bin/sudo", "/sbin/shutdown", "-h", "now"],
                check=True,
            )
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to shut down: {e}")

    def schedule_wakeup(self, minutes: int, dynamic: bool = True) -> bool:
        """Schedule a wakeup using PiJuice.

        Args:
            minutes: Base minutes from now to wake up
            dynamic: Whether to dynamically adjust wakeup time based on battery level

        Returns:
            True if wakeup was scheduled successfully, False otherwise
            
        Raises:
            WakeupSchedulingError: If wakeup scheduling fails
        """
        if not self._pijuice_adapter:
            logger.info(f"Mock wakeup: Would schedule wakeup in {minutes} minutes")
            return True

        # Use power controller for dynamic calculation if available
        if dynamic and self._power_controller:
            minutes = self._power_controller.calculate_sleep_time()

        wake_time = datetime.now() + timedelta(minutes=minutes)
        
        try:
            return self._pijuice_adapter.set_alarm(wake_time)
        except WakeupSchedulingError:
            logger.error(f"Failed to schedule wakeup for {wake_time}")
            raise

    # System metrics
    def get_system_metrics(self) -> dict[str, float]:
        """Get comprehensive system metrics.

        Returns:
            Dictionary containing system metrics
        """
        return self._metrics_collector.get_system_metrics()

    # Event configuration delegation
    def get_event_configuration(self, event_type: str) -> dict[str, object]:
        """Get configuration for a specific event.

        Args:
            event_type: Event type to query

        Returns:
            Event configuration data
        """
        if not self._pijuice_adapter:
            return {}

        # Convert string to PiJuiceEvent
        from rpi_weather_display.utils.pijuice_adapter import PiJuiceEvent

        try:
            event = PiJuiceEvent(event_type)
            result = self._pijuice_adapter.get_event_configuration(event)
            return dict(result)  # Convert TypedDict to regular dict
        except ValueError:
            logger.error(f"Invalid event type: {event_type}")
            return {}

    # State change callbacks
    def register_state_change_callback(
        self,
        callback: "Callable[[PowerState, PowerState], None]",
    ) -> "PowerStateCallback | None":
        """Register a callback for power state changes.

        Args:
            callback: Function to call when state changes

        Returns:
            Callback wrapper object
        """
        if not self._power_controller:
            return None
        return self._power_controller.register_state_change_callback(callback)

    def unregister_state_change_callback(self, callback_obj: "PowerStateCallback") -> None:
        """Unregister a power state change callback.

        Args:
            callback_obj: Callback wrapper to remove
        """
        if self._power_controller and callback_obj:
            self._power_controller.unregister_state_change_callback(callback_obj)

