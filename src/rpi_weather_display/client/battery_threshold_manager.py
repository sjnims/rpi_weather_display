"""Battery-aware threshold management for display refresh optimization.

Provides intelligent threshold adjustments based on battery status to
optimize power consumption during display updates.
"""

from typing import TYPE_CHECKING

from rpi_weather_display.constants import BATTERY_EMPTY_THRESHOLD, BATTERY_WARNING_THRESHOLD
from rpi_weather_display.models.system import BatteryState, BatteryStatus

if TYPE_CHECKING:
    from rpi_weather_display.models.config import DisplayConfig


class BatteryThresholdManager:
    """Manages battery-aware thresholds for display refresh decisions.
    
    This class encapsulates the logic for determining appropriate refresh
    thresholds based on current battery status, helping to extend battery
    life by reducing refresh frequency when power is low.
    
    Attributes:
        config: Display configuration with threshold settings
        _current_battery_status: Current battery status for threshold decisions
    """
    
    def __init__(self, config: "DisplayConfig") -> None:
        """Initialize the battery threshold manager.
        
        Args:
            config: Display configuration containing threshold settings
        """
        self.config = config
        self._current_battery_status: BatteryStatus | None = None
        
    def update_battery_status(self, battery_status: BatteryStatus) -> None:
        """Update the current battery status.
        
        Args:
            battery_status: Current battery status including level and state
        """
        self._current_battery_status = battery_status
        
    def get_pixel_diff_threshold(self) -> int:
        """Get the pixel difference threshold based on battery status.
        
        Determines how different a pixel must be before it's considered "changed".
        Higher thresholds reduce refresh frequency at the cost of potential
        minor display inconsistencies.
        
        Threshold values by battery status:
        - Charging: standard threshold from config
        - Critical battery (≤10%): highest threshold to minimize refreshes
        - Low battery (≤20%): elevated threshold to reduce refreshes
        - Normal battery: standard threshold from config
        
        Returns:
            Pixel difference threshold (0-255), higher values require larger
            differences to trigger refresh
        """
        if not self._should_use_battery_aware_thresholds():
            return self.config.pixel_diff_threshold
            
        battery = self._current_battery_status
        if battery is None:
            return self.config.pixel_diff_threshold
            
        # Determine threshold based on battery state and level
        if battery.state == BatteryState.CHARGING:
            return self.config.pixel_diff_threshold
        elif (
            battery.state == BatteryState.DISCHARGING 
            and battery.level <= BATTERY_EMPTY_THRESHOLD
        ):
            return self.config.pixel_diff_threshold_critical_battery
        elif (
            battery.state == BatteryState.DISCHARGING 
            and battery.level <= BATTERY_WARNING_THRESHOLD
        ):
            return self.config.pixel_diff_threshold_low_battery
        else:
            return self.config.pixel_diff_threshold
            
    def get_min_changed_pixels(self) -> int:
        """Get minimum changed pixels required based on battery status.
        
        Works together with pixel difference threshold to determine when
        a display refresh should occur. Even if pixels exceed the difference
        threshold, the total count must exceed this minimum.
        
        Minimum counts by battery status:
        - Charging: standard minimum from config
        - Critical battery (≤10%): highest minimum to minimize refreshes
        - Low battery (≤20%): elevated minimum to reduce refreshes
        - Normal battery: standard minimum from config
        
        Returns:
            Minimum number of changed pixels required to trigger refresh
        """
        if not self._should_use_battery_aware_thresholds():
            return self.config.min_changed_pixels
            
        battery = self._current_battery_status
        if battery is None:
            return self.config.min_changed_pixels
            
        # Determine minimum based on battery state and level
        if battery.state == BatteryState.CHARGING:
            return self.config.min_changed_pixels
        elif (
            battery.state == BatteryState.DISCHARGING 
            and battery.level <= BATTERY_EMPTY_THRESHOLD
        ):
            return self.config.min_changed_pixels_critical_battery
        elif (
            battery.state == BatteryState.DISCHARGING 
            and battery.level <= BATTERY_WARNING_THRESHOLD
        ):
            return self.config.min_changed_pixels_low_battery
        else:
            return self.config.min_changed_pixels
            
    def _should_use_battery_aware_thresholds(self) -> bool:
        """Check if battery-aware thresholds should be used.
        
        Returns:
            True if battery-aware thresholds are enabled and battery status is available
        """
        return (
            self.config.battery_aware_threshold and 
            self._current_battery_status is not None
        )