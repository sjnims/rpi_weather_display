"""System status models for hardware components and system metrics.

Defines Pydantic models for battery status, network conditions, and overall
system information used for monitoring the Raspberry Pi's state.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class BatteryState(str, Enum):
    """Battery state enum."""

    CHARGING = "charging"
    DISCHARGING = "discharging"
    FULL = "full"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str) -> "BatteryState":
        """Create BatteryState from string value.

        Args:
            value: String representation of battery state

        Returns:
            BatteryState enum value
        """
        value_upper = value.upper()
        if "CHARGING" in value_upper:
            return cls.CHARGING
        if "NORMAL" in value_upper or "DISCHARGING" in value_upper:
            return cls.DISCHARGING
        if "CHARGED" in value_upper or "FULL" in value_upper:
            return cls.FULL
        return cls.UNKNOWN


class BatteryStatus(BaseModel):
    """Battery status information."""

    level: int  # Percentage
    voltage: float  # Volts
    current: float  # mA
    temperature: float  # Celsius
    state: BatteryState = BatteryState.UNKNOWN
    time_remaining: int | None = None  # Minutes
    timestamp: datetime | None = Field(default_factory=datetime.now)  # When this reading was taken

    @property
    def is_low(self) -> bool:
        """Check if battery level is low.

        This property determines if the battery level is considered low (below 20%)
        and the device is currently discharging.

        Returns:
            True if battery level is below 20% and discharging, False otherwise.
        """
        return self.level < 20 and self.state == BatteryState.DISCHARGING

    @property
    def is_critical(self) -> bool:
        """Check if battery level is critical.

        This property determines if the battery level is considered critically low
        (below 10%) and the device is currently discharging.

        Returns:
            True if battery level is below 10% and discharging, False otherwise.
        """
        return self.level < 10 and self.state == BatteryState.DISCHARGING


class NetworkState(str, Enum):
    """Network state enum."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"


class NetworkStatus(BaseModel):
    """Network status information."""

    state: NetworkState = NetworkState.DISCONNECTED
    ssid: str | None = None
    ip_address: str | None = None
    signal_strength: int | None = None  # dBm
    last_connection: datetime | None = None


class SystemStatus(BaseModel):
    """System status information."""

    hostname: str
    uptime: int  # Seconds
    cpu_temp: float  # Celsius
    cpu_usage: float  # Percentage
    memory_usage: float  # Percentage
    disk_usage: float  # Percentage
    battery: BatteryStatus
    network: NetworkStatus
    last_updated: datetime = Field(default_factory=datetime.now)
    last_refresh: datetime | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
