from datetime import datetime
from enum import Enum, auto
from typing import Dict, Optional

from pydantic import BaseModel, Field


class BatteryState(str, Enum):
    """Battery state enum."""
    CHARGING = "charging"
    DISCHARGING = "discharging"
    FULL = "full"
    UNKNOWN = "unknown"


class BatteryStatus(BaseModel):
    """Battery status information."""
    level: int  # Percentage
    voltage: float  # Volts
    current: float  # mA
    temperature: float  # Celsius
    state: BatteryState = BatteryState.UNKNOWN
    time_remaining: Optional[int] = None  # Minutes

    @property
    def is_low(self) -> bool:
        """Check if battery level is low."""
        return self.level < 20 and self.state == BatteryState.DISCHARGING

    @property
    def is_critical(self) -> bool:
        """Check if battery level is critical."""
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
    ssid: Optional[str] = None
    ip_address: Optional[str] = None
    signal_strength: Optional[int] = None  # dBm
    last_connection: Optional[datetime] = None


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
    last_refresh: Optional[datetime] = None
    metrics: Dict[str, float] = Field(default_factory=dict)