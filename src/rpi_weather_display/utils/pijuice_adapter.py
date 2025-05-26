"""PiJuice hardware adapter for the Raspberry Pi weather display.

Provides a clean interface to the PiJuice HAT hardware, handling all
low-level communication and API translation.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, TypedDict, cast

if TYPE_CHECKING:
    from pijuice import PiJuice  # pyright: ignore[reportMissingModuleSource]

from rpi_weather_display.constants import (
    PIJUICE_STATUS_OK,
    PIJUICE_YEAR_OFFSET,
)
from rpi_weather_display.exceptions import WakeupSchedulingError, chain_exception

logger = logging.getLogger(__name__)


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


class PiJuiceAction(str, Enum):
    """PiJuice actions for events."""

    NO_ACTION = "NO_ACTION"
    SYSTEM_HALT = "SYSTEM_HALT"
    SYSTEM_HALT_POW_OFF = "SYSTEM_HALT_POW_OFF"
    SYSTEM_POWER_OFF = "SYSTEM_POWER_OFF"
    SYSTEM_POWER_ON = "SYSTEM_POWER_ON"
    SYSTEM_REBOOT = "SYSTEM_REBOOT"
    SYSTEM_WAKEUP = "SYSTEM_WAKEUP"


class PiJuiceEventData(TypedDict, total=False):
    """Type definition for PiJuice event configuration data."""

    enabled: bool
    function: str | int
    trigger_level: int
    trigger_delay: int
    trigger_value: int
    wakeup_delay: int
    power_delay: int
    delay: int  # For system task parameters
    parameter: int | dict[str, str | int]  # For button configuration


class PiJuiceStatusData(TypedDict, total=False):
    """Type definition for PiJuice status data."""

    battery: str
    chargeLevel: int
    batteryVoltage: int
    batteryCurrent: int
    batteryTemperature: int
    powerInput: str
    powerInput5vIo: str
    isFault: bool


class PiJuiceStatus(TypedDict):
    """Type definition for PiJuice status response."""

    error: str
    data: PiJuiceStatusData


class PiJuiceResponse(TypedDict):
    """Type definition for PiJuice API response."""

    error: str
    data: PiJuiceEventData | PiJuiceStatusData | int | str | bool


class PiJuiceAdapter:
    """Adapter for PiJuice hardware interface."""

    def __init__(self, pijuice_instance: "PiJuice | None" = None) -> None:
        """Initialize PiJuice adapter.

        Args:
            pijuice_instance: Optional PiJuice instance for dependency injection
        """
        self.pijuice: PiJuice | None = pijuice_instance
        self._initialized = False

    def initialize(self, bus: int = 1, address: int = 0x14) -> bool:
        """Initialize PiJuice hardware connection.

        Args:
            bus: I2C bus number
            address: I2C address

        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True

        if self.pijuice:
            # Already have an instance (for testing)
            self._initialized = True
            return True

        try:
            # Import PiJuice only when needed (hardware dependency)
            from pijuice import PiJuice  # type: ignore[import-not-found]

            self.pijuice = PiJuice(bus, address)

            # Test connection
            status = self.get_status()
            if status["error"] != PIJUICE_STATUS_OK:
                logger.error(f"PiJuice initialization failed: {status['error']}")
                return False

            logger.info("PiJuice initialized successfully")
            self._initialized = True
            return True

        except ImportError:
            logger.warning("PiJuice library not available")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize PiJuice: {e}")
            return False

    def get_status(self) -> PiJuiceStatus:
        """Get PiJuice status.

        Returns:
            Status response with error code and data
        """
        if not self.pijuice:
            return {"error": "NOT_INITIALIZED", "data": {}}

        try:
            result = self.pijuice.status.GetStatus()
            # Cast to our specific type
            return cast(PiJuiceStatus, result)
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return {"error": str(e), "data": {}}

    def get_charge_level(self) -> PiJuiceResponse:
        """Get battery charge level.

        Returns:
            Response with charge level percentage
        """
        if not self.pijuice:
            return {"error": "NOT_INITIALIZED", "data": 0}

        try:
            result = self.pijuice.status.GetChargeLevel()
            # Cast to our specific type
            return cast(PiJuiceResponse, result)
        except Exception as e:
            logger.error(f"Failed to get charge level: {e}")
            return {"error": str(e), "data": 0}

    def get_battery_voltage(self) -> PiJuiceResponse:
        """Get battery voltage in millivolts.

        Returns:
            Response with voltage in millivolts
        """
        if not self.pijuice:
            return {"error": "NOT_INITIALIZED", "data": 0}

        try:
            result = self.pijuice.status.GetBatteryVoltage()
            # Cast to our specific type
            return cast(PiJuiceResponse, result)
        except Exception as e:
            logger.error(f"Failed to get battery voltage: {e}")
            return {"error": str(e), "data": 0}

    def get_battery_current(self) -> PiJuiceResponse:
        """Get battery current in milliamps.

        Returns:
            Response with current in milliamps
        """
        if not self.pijuice:
            return {"error": "NOT_INITIALIZED", "data": 0}

        try:
            result = self.pijuice.status.GetBatteryCurrent()
            # Cast to our specific type
            return cast(PiJuiceResponse, result)
        except Exception as e:
            logger.error(f"Failed to get battery current: {e}")
            return {"error": str(e), "data": 0}

    def get_battery_temperature(self) -> PiJuiceResponse:
        """Get battery temperature in Celsius.

        Returns:
            Response with temperature in Celsius
        """
        if not self.pijuice:
            return {"error": "NOT_INITIALIZED", "data": 0}

        try:
            result = self.pijuice.status.GetBatteryTemperature()
            # Cast to our specific type
            return cast(PiJuiceResponse, result)
        except Exception as e:
            logger.error(f"Failed to get battery temperature: {e}")
            return {"error": str(e), "data": 0}

    def set_alarm(self, wakeup_time: datetime) -> bool:
        """Set RTC alarm for wakeup.

        Args:
            wakeup_time: Time to wake up

        Returns:
            True if alarm set successfully, False otherwise
            
        Raises:
            WakeupSchedulingError: If alarm cannot be set
        """
        if not self.pijuice:
            raise WakeupSchedulingError(
                "Cannot set alarm: PiJuice not initialized",
                {"target_time": wakeup_time.isoformat()}
            )

        try:
            alarm_config = {
                "second": wakeup_time.second,
                "minute": wakeup_time.minute,
                "hour": wakeup_time.hour,
                "day": wakeup_time.day,
                "month": wakeup_time.month,
                "year": wakeup_time.year - PIJUICE_YEAR_OFFSET,
            }

            response = self.pijuice.rtcAlarm.SetAlarm(alarm_config)
            if response.get("error") != PIJUICE_STATUS_OK:
                raise WakeupSchedulingError(
                    f"Failed to set RTC alarm: {response.get('error', 'Unknown error')}",
                    {
                        "target_time": wakeup_time.isoformat(),
                        "alarm_config": alarm_config,
                        "response": response
                    }
                )
                
            response = self.pijuice.rtcAlarm.SetWakeupEnabled(True)
            if response.get("error") != PIJUICE_STATUS_OK:
                raise WakeupSchedulingError(
                    f"Failed to enable wakeup: {response.get('error', 'Unknown error')}",
                    {
                        "target_time": wakeup_time.isoformat(),
                        "alarm_config": alarm_config,
                        "response": response
                    }
                )

            logger.info(f"Alarm set for {wakeup_time}")
            return True

        except WakeupSchedulingError:
            # Re-raise our exceptions as-is
            raise
        except Exception as e:
            raise chain_exception(
                WakeupSchedulingError(
                    "Failed to schedule wakeup",
                    {
                        "target_time": wakeup_time.isoformat(),
                        "error": str(e)
                    }
                ),
                e
            ) from None

    def disable_wakeup(self) -> bool:
        """Disable wakeup alarm.

        Returns:
            True if disabled successfully, False otherwise
        """
        if not self.pijuice:
            return False

        try:
            response = self.pijuice.wakeUpOnCharge.SetWakeupEnabled(False)
            return response["error"] == PIJUICE_STATUS_OK
        except Exception as e:
            logger.error(f"Failed to disable wakeup: {e}")
            return False

    def set_power_switch(self, state: int) -> bool:
        """Set system power switch state.

        Args:
            state: Power switch state (0=off, 1=on)

        Returns:
            True if set successfully, False otherwise
        """
        if not self.pijuice:
            return False

        try:
            response = self.pijuice.power.SetSystemPowerSwitch(state)
            return response["error"] == PIJUICE_STATUS_OK
        except Exception as e:
            logger.error(f"Failed to set power switch: {e}")
            return False

    def configure_event(self, event: PiJuiceEvent, action: PiJuiceAction, delay: int = 0) -> bool:
        """Configure PiJuice event behavior.

        Args:
            event: Event type to configure
            action: Action to perform
            delay: Delay in seconds before action

        Returns:
            True if configured successfully, False otherwise
        """
        if not self.pijuice:
            return False

        try:
            if event in [
                PiJuiceEvent.LOW_CHARGE,
                PiJuiceEvent.LOW_BATTERY,
                PiJuiceEvent.NO_BATTERY,
            ]:
                # System task parameters
                response = self.pijuice.config.SetSystemTaskParameters(
                    event.value, action.value, delay
                )
            elif "BUTTON" in event.value:
                # Button configuration
                button_num = event.value.split("_")[1]  # Extract SW1, SW2, SW3
                # PRESS, RELEASE, LONG_PRESS
                event_type = "_".join(event.value.split("_")[2:])

                response = self.pijuice.config.SetButtonConfiguration(
                    button_num, event_type, {"function": action.value, "parameter": delay}
                )
            else:
                logger.warning(f"Unknown event type: {event}")
                return False

            return response["error"] == PIJUICE_STATUS_OK

        except Exception as e:
            logger.error(f"Failed to configure event {event}: {e}")
            return False

    def get_event_configuration(self, event: PiJuiceEvent) -> PiJuiceEventData:
        """Get configuration for a specific event.

        Args:
            event: Event type to query

        Returns:
            Event configuration data
        """
        if not self.pijuice:
            return cast(PiJuiceEventData, {})

        try:
            if event in [
                PiJuiceEvent.LOW_CHARGE,
                PiJuiceEvent.LOW_BATTERY,
                PiJuiceEvent.NO_BATTERY,
            ]:
                # System task parameters
                response = self.pijuice.config.GetSystemTaskParameters(event.value)
            elif "BUTTON" in event.value:
                # Button configuration
                button_num = event.value.split("_")[1]
                event_type = "_".join(event.value.split("_")[2:])

                response = self.pijuice.config.GetButtonConfiguration(button_num, event_type)
            else:
                logger.warning(f"Unknown event type: {event}")
                return cast(PiJuiceEventData, {})

            if response["error"] == PIJUICE_STATUS_OK and isinstance(response["data"], dict):
                return cast(PiJuiceEventData, response["data"])

            return cast(PiJuiceEventData, {})

        except Exception as e:
            logger.error(f"Failed to get event configuration for {event}: {e}")
            return cast(PiJuiceEventData, {})

    def is_initialized(self) -> bool:
        """Check if PiJuice is initialized.

        Returns:
            True if initialized, False otherwise
        """
        return self._initialized and self.pijuice is not None
