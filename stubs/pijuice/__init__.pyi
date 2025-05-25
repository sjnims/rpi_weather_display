"""Type stubs for the PiJuice library."""
# ruff: noqa: N802, N803, N815  # Ignore naming conventions - external API

from typing import TypedDict

# The PiJuice API returns different data types depending on the method called.
# We define a union type that covers all possible return types to avoid using Any.
PiJuiceDataType = int | str | bool | dict[str, int | str | bool]

class PiJuiceAPIResponse(TypedDict):
    """Standard response format from PiJuice API calls.

    All PiJuice API methods return this structure with:
    - error: Status code (e.g., 'NO_ERROR', 'COMMUNICATION_ERROR')
    - data: The actual data, which varies by method

    Note: Our pijuice_adapter.py defines more specific response types
    for better type safety in the application code.
    """

    error: str
    data: PiJuiceDataType

class StatusAPI:
    """PiJuice Status API."""

    def GetStatus(self) -> PiJuiceAPIResponse:
        """Get general status information."""
        ...

    def GetChargeLevel(self) -> PiJuiceAPIResponse:
        """Get battery charge level percentage."""
        ...

    def GetBatteryVoltage(self) -> PiJuiceAPIResponse:
        """Get battery voltage in millivolts."""
        ...

    def GetBatteryCurrent(self) -> PiJuiceAPIResponse:
        """Get battery current in milliamps."""
        ...

    def GetIoCurrent(self) -> PiJuiceAPIResponse:
        """Get IO current in milliamps."""
        ...

    def GetBatteryTemperature(self) -> PiJuiceAPIResponse:
        """Get battery temperature in Celsius."""
        ...

    def GetChargeStatus(self) -> PiJuiceAPIResponse:
        """Get battery charging status."""
        ...

    def GetFaultStatus(self) -> PiJuiceAPIResponse:
        """Get fault status."""
        ...

class PowerAPI:
    """PiJuice Power API."""

    def SetSystemPowerSwitch(self, state: int) -> PiJuiceAPIResponse:
        """Set system power switch state (0=off, 1=on)."""
        ...

    def GetSystemPowerSwitch(self) -> PiJuiceAPIResponse:
        """Get system power switch state."""
        ...

    def SetPowerOff(self, delay: int) -> PiJuiceAPIResponse:
        """Schedule power off after delay seconds."""
        ...

    def GetPowerOff(self) -> PiJuiceAPIResponse:
        """Get power off configuration."""
        ...

class WakeUpOnChargeAPI:
    """PiJuice Wake Up On Charge API."""

    def SetWakeupEnabled(self, enabled: bool) -> PiJuiceAPIResponse:
        """Enable or disable wakeup on charge."""
        ...

    def GetWakeupEnabled(self) -> PiJuiceAPIResponse:
        """Get wakeup on charge status."""
        ...

class ConfigAPI:
    """PiJuice Configuration API."""

    def SetSystemTaskParameters(self, event: str, action: str, delay: int) -> PiJuiceAPIResponse:
        """Set system task parameters for events."""
        ...

    def GetSystemTaskParameters(self, event: str) -> PiJuiceAPIResponse:
        """Get system task parameters for an event."""
        ...

    def SetButtonConfiguration(
        self, button: str, event_type: str, config: dict[str, str | int]
    ) -> PiJuiceAPIResponse:
        """Set button configuration."""
        ...

    def GetButtonConfiguration(self, button: str, event_type: str) -> PiJuiceAPIResponse:
        """Get button configuration."""
        ...

    def SetChargeMode(self, mode: str) -> PiJuiceAPIResponse:
        """Set battery charge mode."""
        ...

    def GetChargeMode(self) -> PiJuiceAPIResponse:
        """Get battery charge mode."""
        ...

class AlarmConfig(TypedDict, total=False):
    """RTC alarm configuration."""

    second: int
    minute: int
    hour: int
    day: int
    month: int
    year: int

class RtcAlarmAPI:
    """PiJuice RTC Alarm API."""

    def SetAlarm(self, alarm: dict[str, int] | AlarmConfig) -> PiJuiceAPIResponse:
        """Set RTC alarm."""
        ...

    def GetAlarm(self) -> PiJuiceAPIResponse:
        """Get RTC alarm configuration."""
        ...

    def SetWakeupEnabled(self, enabled: bool) -> PiJuiceAPIResponse:
        """Enable or disable RTC wakeup."""
        ...

    def GetWakeupEnabled(self) -> PiJuiceAPIResponse:
        """Get RTC wakeup status."""
        ...

    def ClearAlarmFlag(self) -> PiJuiceAPIResponse:
        """Clear RTC alarm flag."""
        ...

class PiJuice:
    """Main PiJuice interface class."""

    status: StatusAPI
    power: PowerAPI
    wakeUpOnCharge: WakeUpOnChargeAPI
    config: ConfigAPI
    rtcAlarm: RtcAlarmAPI

    def __init__(self, bus: int = 1, address: int = 0x14) -> None:
        """Initialize PiJuice interface.

        Args:
            bus: I2C bus number
            address: I2C address
        """
        ...
