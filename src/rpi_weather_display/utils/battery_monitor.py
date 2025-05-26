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
from rpi_weather_display.exceptions import (
    BatteryMonitoringError,
    CriticalBatteryError,
    PiJuiceCommunicationError,
    PiJuiceInitializationError,
    chain_exception,
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
    from rpi_weather_display.utils.pijuice_adapter import PiJuiceAdapter, PiJuiceResponse

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

    def _get_development_battery_status(self) -> BatteryStatus:
        """Get mock battery status for development mode.
        
        Returns:
            Mock battery status with predefined values
        """
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
    
    def _get_default_battery_status(self) -> BatteryStatus:
        """Get default battery status when PiJuice is not available.
        
        Returns:
            Battery status with zero/unknown values
        """
        logger.warning("PiJuice not available, returning unknown battery status")
        return BatteryStatus(
            level=0,
            voltage=0.0,
            current=0.0,
            temperature=0.0,
            state=BatteryState.UNKNOWN,
            timestamp=datetime.now(),
        )
    
    def _extract_pijuice_value(
        self, response: "PiJuiceResponse", default: float = 0.0, divisor: float = 1.0
    ) -> float:
        """Extract numeric value from PiJuice response.
        
        Args:
            response: PiJuice API response dict
            default: Default value if extraction fails
            divisor: Divisor to apply to the value (e.g., 1000 for mV to V conversion)
            
        Returns:
            Extracted float value or default
        """
        if response.get("error") == PIJUICE_STATUS_OK:
            data = response.get("data")
            if isinstance(data, int | float):
                return float(data) / divisor
            if isinstance(data, str):
                try:
                    return float(data) / divisor
                except ValueError:
                    logger.warning(
                        "Invalid string value in PiJuice response",
                        extra={"value": data, "response": response}
                    )
        return default
    
    def _get_pijuice_data(self) -> tuple[dict[str, Any], int, float, float, float]:
        """Retrieve all data from PiJuice hardware.
        
        Returns:
            Tuple of (status_data, charge_level, voltage, current, temperature)
        """
        # Get all responses from PiJuice
        if self.pijuice is None:
            raise PiJuiceInitializationError(
                "PiJuice adapter is not available",
                {"operation": "get_battery_data", "adapter_present": False}
            )
        
        try:
            status_response = self.pijuice.get_status()
            charge_response = self.pijuice.get_charge_level()
            voltage_response = self.pijuice.get_battery_voltage()
            current_response = self.pijuice.get_battery_current()
            temp_response = self.pijuice.get_battery_temperature()
        except Exception as e:
            raise chain_exception(
                PiJuiceCommunicationError(
                    "Failed to communicate with PiJuice hardware",
                    {"operation": "get_battery_data", "error": str(e)}
                ),
                e
            ) from e
        
        # Extract status data
        status_data = (
            dict(status_response["data"]) 
            if status_response.get("error") == PIJUICE_STATUS_OK 
            else {}
        )
        
        # Extract numeric values
        charge_level = int(self._extract_pijuice_value(charge_response))
        voltage = self._extract_pijuice_value(voltage_response, divisor=1000.0)  # mV to V
        current = self._extract_pijuice_value(current_response)
        temperature = self._extract_pijuice_value(temp_response)
        
        return status_data, charge_level, voltage, current, temperature
    
    def _determine_battery_state(
        self, status_data: dict[str, Any], charge_level: int
    ) -> BatteryState:
        """Determine battery state from PiJuice status data.
        
        Args:
            status_data: PiJuice status data dictionary
            charge_level: Current battery charge level (0-100)
            
        Returns:
            Determined battery state
        """
        battery_status_str = str(status_data.get("battery", "UNKNOWN"))
        power_input = str(status_data.get("powerInput", "UNKNOWN"))
        is_fault = bool(status_data.get("isFault", False))
        
        # Log fault conditions
        if is_fault:
            logger.warning(
                "PiJuice fault detected",
                extra={
                    "battery_state": battery_status_str,
                    "power_input": power_input,
                    "io_voltage": str(status_data.get("powerInput5vIo", "UNKNOWN")),
                    "charge_level": charge_level,
                },
            )
        
        # Special case: battery might be fully charged
        if battery_status_str == "NORMAL" and power_input == "PRESENT" and charge_level >= 95:
            logger.debug(
                "Battery likely fully charged (power present, high charge level)",
                extra={"charge_level": charge_level, "power_input": power_input},
            )
            return BatteryState.CHARGING
        
        # Log power input but battery not charging
        if power_input in ["PRESENT", "WEAK"] and battery_status_str not in [
            "CHARGING_FROM_IN",
            "CHARGING_FROM_5V_IO",
        ]:
            logger.debug(
                "Power input detected but battery not charging",
                extra={
                    "power_input": power_input,
                    "battery_state": battery_status_str,
                    "charge_level": charge_level,
                },
            )
        
        return BatteryState.from_string(battery_status_str)
    
    def _update_battery_history(self, status: BatteryStatus) -> None:
        """Update battery history and calculate drain rate.
        
        Args:
            status: Current battery status
        """
        if status.level <= 0:
            return
            
        self._battery_history.append(status)
        
        # Calculate drain rate if we have enough history
        if len(self._battery_history) >= 2:
            drain_rate = calculate_drain_rate(list(self._battery_history))
            if drain_rate is not None:
                self._current_drain_rate = (
                    DRAIN_WEIGHT_NEW * drain_rate
                    + DRAIN_WEIGHT_PREV * self._current_drain_rate
                )
        
        self._last_battery_update = datetime.now()
    
    def get_battery_status(self) -> BatteryStatus:
        """Get comprehensive battery status information.

        Returns:
            Battery status with charge level, state, voltage, current, and health metrics
        """
        if self.config.development_mode:
            return self._get_development_battery_status()

        if not self.pijuice:
            return self._get_default_battery_status()

        try:
            # Get all data from PiJuice
            status_data, charge_level, voltage, current, temperature = self._get_pijuice_data()
            
            # Determine battery state
            state = self._determine_battery_state(status_data, charge_level)

            # Create status object
            status = BatteryStatus(
                level=charge_level,
                voltage=voltage,
                current=current,
                temperature=temperature,
                state=state,
                timestamp=datetime.now(),
            )

            # Store additional diagnostic info as private attributes
            power_input = str(status_data.get("powerInput", "UNKNOWN"))
            io_voltage = str(status_data.get("powerInput5vIo", "UNKNOWN"))
            is_fault = bool(status_data.get("isFault", False))
            
            status._pijuice_fault = is_fault  # type: ignore[attr-defined]
            status._power_input = power_input  # type: ignore[attr-defined]
            status._io_voltage = io_voltage  # type: ignore[attr-defined]

            # Update battery history and drain rate
            self._update_battery_history(status)

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

        except (PiJuiceInitializationError, PiJuiceCommunicationError):
            # Re-raise PiJuice-specific errors as they're critical
            raise
        except Exception as e:
            logger.error(f"Failed to get battery status: {e}")
            raise chain_exception(
                BatteryMonitoringError(
                    "Failed to read battery status",
                    {"source": "pijuice", "error": str(e)}
                ),
                e
            ) from e

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

        except (PiJuiceInitializationError, PiJuiceCommunicationError, BatteryMonitoringError):
            # Re-raise battery-specific errors
            raise
        except Exception as e:
            logger.error(f"Failed to calculate battery life: {e}")
            raise chain_exception(
                BatteryMonitoringError(
                    "Failed to calculate battery life",
                    {"source": "battery_life_calculation", "error": str(e)}
                ),
                e
            ) from e

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
        except (PiJuiceInitializationError, PiJuiceCommunicationError, BatteryMonitoringError):
            # Re-raise battery-specific errors
            raise
        except Exception as e:
            logger.error(f"Failed to check discharge rate: {e}")
            raise chain_exception(
                BatteryMonitoringError(
                    "Failed to check discharge rate",
                    {"source": "discharge_rate_check", "error": str(e)}
                ),
                e
            ) from e

    def should_conserve_power(self) -> bool:
        """Check if power conservation is needed based on battery status.

        Returns:
            True if power should be conserved, False otherwise
        """
        try:
            status = self.get_battery_status()
            return should_conserve_power(status, self.config.power)
        except (PiJuiceInitializationError, PiJuiceCommunicationError, BatteryMonitoringError):
            # Re-raise battery-specific errors
            raise
        except Exception as e:
            logger.error(f"Failed to check power conservation: {e}")
            raise chain_exception(
                BatteryMonitoringError(
                    "Failed to check power conservation status",
                    {"source": "power_conservation_check", "error": str(e)}
                ),
                e
            ) from e

    def is_battery_critical(self) -> bool:
        """Check if battery is at critical level.

        Returns:
            True if battery is critical, False otherwise
        """
        try:
            status = self.get_battery_status()
            is_critical = is_battery_critical(status, self.config.power.critical_battery_threshold)
            
            # If battery is critical, raise specific exception
            if is_critical:
                raise CriticalBatteryError(
                    "Battery critically low - immediate action required",
                    {
                        "level": status.level,
                        "threshold": self.config.power.critical_battery_threshold,
                        "voltage": status.voltage
                    }
                )
            
            return False
        except CriticalBatteryError:
            # Re-raise critical battery errors
            raise
        except (PiJuiceInitializationError, PiJuiceCommunicationError, BatteryMonitoringError):
            # Re-raise battery-specific errors
            raise
        except Exception as e:
            logger.error(f"Failed to check critical battery: {e}")
            raise chain_exception(
                BatteryMonitoringError(
                    "Failed to check critical battery status",
                    {"source": "critical_battery_check", "error": str(e)}
                ),
                e
            ) from e

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
        except (PiJuiceInitializationError, PiJuiceCommunicationError, BatteryMonitoringError):
            # Re-raise battery-specific errors
            raise
        except Exception as e:
            logger.error(f"Failed to get diagnostic info: {e}")
            raise chain_exception(
                BatteryMonitoringError(
                    "Failed to get diagnostic information",
                    {"source": "diagnostic_info", "error": str(e)}
                ),
                e
            ) from e
