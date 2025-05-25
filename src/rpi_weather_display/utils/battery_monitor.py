"""Battery monitoring module for the Raspberry Pi weather display.

Handles battery status monitoring, charge level tracking, and battery health metrics.
"""

import logging
from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING, Any

from rpi_weather_display.constants import (
    ABNORMAL_DISCHARGE_FACTOR,
    BATTERY_HISTORY_SIZE,
    DEFAULT_DRAIN_RATE,
    DRAIN_WEIGHT_NEW,
    DRAIN_WEIGHT_PREV,
    MOCK_BATTERY_CURRENT,
    MOCK_BATTERY_LEVEL,
    MOCK_BATTERY_TEMPERATURE,
    MOCK_BATTERY_VOLTAGE,
    PIJUICE_STATUS_OK,
)
from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.models.system import BatteryState, BatteryStatus
from rpi_weather_display.utils.battery_utils import (
    calculate_drain_rate,
    is_battery_critical,
    is_charging,
    is_discharge_rate_abnormal,
    should_conserve_power,
)

if TYPE_CHECKING:
    from rpi_weather_display.utils.pijuice_adapter import PiJuiceAdapter, PiJuiceStatusData

logger = logging.getLogger(__name__)


class BatteryMonitor:
    """Monitors battery status and health metrics."""

    def __init__(self, config: AppConfig, pijuice_adapter: "PiJuiceAdapter | None" = None) -> None:
        """Initialize battery monitor.

        Args:
            config: Application configuration
            pijuice_adapter: Optional PiJuice adapter for hardware access
        """
        self.config = config
        self.pijuice = pijuice_adapter
        self._battery_history: deque[BatteryStatus] = deque(maxlen=BATTERY_HISTORY_SIZE)
        self._current_drain_rate = DEFAULT_DRAIN_RATE
        self._last_battery_update: datetime | None = None

    def get_battery_status(self) -> BatteryStatus:
        """Get comprehensive battery status information.

        Returns:
            Battery status with charge level, state, voltage, current, and health metrics
        """
        if self.config.development_mode:
            status = BatteryStatus(
                level=MOCK_BATTERY_LEVEL,
                voltage=MOCK_BATTERY_VOLTAGE,
                current=MOCK_BATTERY_CURRENT,
                temperature=MOCK_BATTERY_TEMPERATURE,
                state=BatteryState.UNKNOWN,
                timestamp=datetime.now(),
            )
            logger.info(
                "Development mode: Using mock battery status", extra={"battery_level": status.level}
            )
            return status

        if not self.pijuice:
            logger.warning("PiJuice not available, returning unknown battery status")
            return BatteryStatus(
                level=0,
                voltage=0.0,
                current=0.0,
                temperature=0.0,
                state=BatteryState.UNKNOWN,
                timestamp=datetime.now(),
            )

        try:
            # Get status from PiJuice
            status_response = self.pijuice.get_status()
            charge_response = self.pijuice.get_charge_level()
            voltage_response = self.pijuice.get_battery_voltage()
            current_response = self.pijuice.get_battery_current()
            temp_response = self.pijuice.get_battery_temperature()

            # Extract values with type assertion
            status_data: PiJuiceStatusData | dict[str, Any] = (
                status_response["data"] if status_response["error"] == PIJUICE_STATUS_OK else {}
            )
            charge_level = (
                int(charge_response["data"])
                if charge_response["error"] == PIJUICE_STATUS_OK
                and isinstance(charge_response["data"], int | float)
                else 0
            )
            voltage = (
                float(voltage_response["data"]) / 1000.0
                if voltage_response["error"] == PIJUICE_STATUS_OK
                and isinstance(voltage_response["data"], int | float)
                else 0.0
            )
            current = (
                float(current_response["data"])
                if current_response["error"] == PIJUICE_STATUS_OK
                and isinstance(current_response["data"], int | float)
                else 0.0
            )
            temperature = (
                float(temp_response["data"])
                if temp_response["error"] == PIJUICE_STATUS_OK
                and isinstance(temp_response["data"], int | float)
                else 0.0
            )

            # Determine battery state from status string
            battery_status_str = str(status_data.get("battery", "UNKNOWN"))

            # Get power and fault info
            power_input = str(status_data.get("powerInput", "UNKNOWN"))
            io_voltage = str(status_data.get("powerInput5vIo", "UNKNOWN"))
            is_fault = bool(status_data.get("isFault", False))

            # Log fault conditions
            if is_fault:
                logger.warning(
                    "PiJuice fault detected",
                    extra={
                        "battery_state": battery_status_str,
                        "power_input": power_input,
                        "io_voltage": io_voltage,
                        "charge_level": charge_level,
                    },
                )

            # Use power input to improve state detection
            if battery_status_str == "NORMAL" and power_input == "PRESENT":
                # Battery might be fully charged if power is present but not charging
                if charge_level >= 95:
                    state = BatteryState.CHARGING
                    logger.debug(
                        "Battery likely fully charged (power present, high charge level)",
                        extra={"charge_level": charge_level, "power_input": power_input},
                    )
                else:
                    state = BatteryState.from_string(battery_status_str)
            elif power_input in ["PRESENT", "WEAK"] and battery_status_str not in [
                "CHARGING_FROM_IN",
                "CHARGING_FROM_5V_IO",
            ]:
                # External power present but battery not charging - log for diagnostics
                logger.debug(
                    "Power input detected but battery not charging",
                    extra={
                        "power_input": power_input,
                        "battery_state": battery_status_str,
                        "charge_level": charge_level,
                    },
                )
                state = BatteryState.from_string(battery_status_str)
            else:
                state = BatteryState.from_string(battery_status_str)

            # Create status object first
            status = BatteryStatus(
                level=charge_level,
                voltage=voltage,
                current=current,
                temperature=temperature,
                state=state,
                timestamp=datetime.now(),
            )

            # Store additional diagnostic info as private attributes
            status._pijuice_fault = is_fault  # type: ignore[attr-defined]
            status._power_input = power_input  # type: ignore[attr-defined]
            status._io_voltage = io_voltage  # type: ignore[attr-defined]

            # Update battery history and calculate drain rate
            if charge_level > 0:
                self._battery_history.append(status)

                # Calculate drain rate
                if len(self._battery_history) >= 2:
                    drain_rate = calculate_drain_rate(list(self._battery_history))
                    if drain_rate is not None:
                        self._current_drain_rate = (
                            DRAIN_WEIGHT_NEW * drain_rate
                            + DRAIN_WEIGHT_PREV * self._current_drain_rate
                        )

                self._last_battery_update = datetime.now()

            logger.info(
                "Battery status retrieved",
                extra={
                    "charge_level": charge_level,
                    "state": state.value,
                    "voltage": voltage,
                    "current": current,
                    "temperature": temperature,
                    "drain_rate": self._current_drain_rate,
                    "power_input": power_input,
                    "is_fault": is_fault,
                },
            )

            return status

        except Exception as e:
            logger.error(f"Failed to get battery status: {e}")
            return BatteryStatus(
                level=0,
                voltage=0.0,
                current=0.0,
                temperature=0.0,
                state=BatteryState.UNKNOWN,
                timestamp=datetime.now(),
            )

    def get_expected_battery_life(self) -> int | None:
        """Calculate expected battery life in hours based on current drain rate.

        Returns:
            Expected hours of battery life, or None if cannot be calculated
        """
        if self.config.development_mode:
            logger.info("Development mode: returning fixed battery life estimate")
            return 24

        try:
            status = self.get_battery_status()

            # Can't calculate if charging or no drain rate
            if is_charging(status) or self._current_drain_rate <= 0:
                return None

            # Calculate remaining capacity in mAh
            remaining_capacity = (status.level / 100.0) * self.config.power.battery_capacity_mah

            # Calculate hours remaining
            hours_remaining = int(remaining_capacity / self._current_drain_rate)

            logger.info(
                "Battery life estimate calculated",
                extra={
                    "hours_remaining": hours_remaining,
                    "charge_level": status.level,
                    "drain_rate_ma": self._current_drain_rate,
                },
            )

            return hours_remaining

        except Exception as e:
            logger.error(f"Failed to calculate battery life: {e}")
            return None

    def is_discharge_rate_abnormal(self) -> bool:
        """Check if the current battery discharge rate is abnormal.

        Returns:
            True if discharge rate is abnormal, False otherwise
        """
        try:
            # Get current status to ensure drain rate is up to date
            status = self.get_battery_status()

            # If there's a fault, consider discharge rate abnormal
            if hasattr(status, "_pijuice_fault") and getattr(status, "_pijuice_fault", False):
                logger.warning("Discharge rate check: PiJuice fault detected")
                return True

            # Use a default expected rate of 2% per hour if not configured
            expected_rate = getattr(self.config.power, "expected_discharge_rate", 2.0)
            return is_discharge_rate_abnormal(
                self._current_drain_rate, expected_rate, ABNORMAL_DISCHARGE_FACTOR
            )
        except Exception as e:
            logger.error(f"Failed to check discharge rate: {e}")
            return False

    def should_conserve_power(self) -> bool:
        """Check if power conservation is needed based on battery status.

        Returns:
            True if power should be conserved, False otherwise
        """
        try:
            status = self.get_battery_status()
            return should_conserve_power(status, self.config.power)
        except Exception as e:
            logger.error(f"Failed to check power conservation: {e}")
            return True  # Conserve power on error

    def is_battery_critical(self) -> bool:
        """Check if battery is at critical level.

        Returns:
            True if battery is critical, False otherwise
        """
        try:
            status = self.get_battery_status()
            return is_battery_critical(status, self.config.power.critical_battery_threshold)
        except Exception as e:
            logger.error(f"Failed to check critical battery: {e}")
            return False

    def get_battery_history(self) -> list[BatteryStatus]:
        """Get battery history for analysis.

        Returns:
            List of battery status readings
        """
        return list(self._battery_history)

    def clear_battery_history(self) -> None:
        """Clear battery history (mainly for testing)."""
        self._battery_history.clear()
        self._last_battery_update = None

    def get_diagnostic_info(self) -> dict[str, Any]:
        """Get diagnostic information from last battery status.

        Returns:
            Dictionary with diagnostic info including power input and fault status
        """
        try:
            status = self.get_battery_status()
            return {
                "power_input": getattr(status, "_power_input", "UNKNOWN"),
                "io_voltage": getattr(status, "_io_voltage", "UNKNOWN"),
                "is_fault": getattr(status, "_pijuice_fault", False),
                "battery_level": status.level,
                "battery_state": status.state.value,
                "drain_rate": self._current_drain_rate,
            }
        except Exception as e:
            logger.error(f"Failed to get diagnostic info: {e}")
            return {}
