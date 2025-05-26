"""Tests for battery threshold manager."""

import sys
from typing import TYPE_CHECKING
from unittest.mock import patch

from rpi_weather_display.client.battery_threshold_manager import BatteryThresholdManager
from rpi_weather_display.models.config import DisplayConfig
from rpi_weather_display.models.system import BatteryState, BatteryStatus

if TYPE_CHECKING:
    pass


class TestBatteryThresholdManager:
    """Test cases for BatteryThresholdManager."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.config = DisplayConfig(
            width=1872,
            height=1404,
            rotate=0,
            vcom=-2.06,
            refresh_interval_minutes=30,
            partial_refresh=True,
            timestamp_format="%Y-%m-%d %H:%M",
            pixel_diff_threshold=10,
            pixel_diff_threshold_low_battery=20,
            pixel_diff_threshold_critical_battery=30,
            min_changed_pixels=100,
            min_changed_pixels_low_battery=250,
            min_changed_pixels_critical_battery=500,
            battery_aware_threshold=True,
        )
        self.manager = BatteryThresholdManager(self.config)

    def test_init(self) -> None:
        """Test initialization."""
        assert self.manager.config == self.config
        assert self.manager._current_battery_status is None

    def test_update_battery_status(self) -> None:
        """Test updating battery status."""
        battery_status = BatteryStatus(
            level=75,
            voltage=3.8,
            current=-500.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager._current_battery_status == battery_status

    def test_get_pixel_diff_threshold_no_battery_aware(self) -> None:
        """Test pixel diff threshold when battery aware is disabled."""
        self.config.battery_aware_threshold = False
        manager = BatteryThresholdManager(self.config)
        assert manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold

    def test_get_pixel_diff_threshold_no_battery_status(self) -> None:
        """Test pixel diff threshold when no battery status is set."""
        # This test covers the case where battery_aware_threshold is True
        # but _current_battery_status is None, so _should_use_battery_aware_thresholds() returns False
        assert self.config.battery_aware_threshold is True
        assert self.manager._current_battery_status is None
        assert not self.manager._should_use_battery_aware_thresholds()
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold

    def test_get_pixel_diff_threshold_charging(self) -> None:
        """Test pixel diff threshold when charging."""
        battery_status = BatteryStatus(
            level=50,
            voltage=3.7,
            current=1000.0,
            temperature=25.0,
            state=BatteryState.CHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold

    def test_get_pixel_diff_threshold_critical_battery(self) -> None:
        """Test pixel diff threshold when battery is critical."""
        battery_status = BatteryStatus(
            level=10,
            voltage=3.5,
            current=-300.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold_critical_battery

    def test_get_pixel_diff_threshold_low_battery(self) -> None:
        """Test pixel diff threshold when battery is low."""
        battery_status = BatteryStatus(
            level=20,
            voltage=3.6,
            current=-400.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold_low_battery

    def test_get_pixel_diff_threshold_normal_battery(self) -> None:
        """Test pixel diff threshold when battery is normal."""
        battery_status = BatteryStatus(
            level=75,
            voltage=3.8,
            current=-500.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold

    def test_get_min_changed_pixels_no_battery_aware(self) -> None:
        """Test min changed pixels when battery aware is disabled."""
        self.config.battery_aware_threshold = False
        manager = BatteryThresholdManager(self.config)
        assert manager.get_min_changed_pixels() == self.config.min_changed_pixels

    def test_get_min_changed_pixels_no_battery_status(self) -> None:
        """Test min changed pixels when no battery status is set."""
        assert self.manager.get_min_changed_pixels() == self.config.min_changed_pixels

    def test_get_min_changed_pixels_charging(self) -> None:
        """Test min changed pixels when charging."""
        battery_status = BatteryStatus(
            level=50,
            voltage=3.7,
            current=1000.0,
            temperature=25.0,
            state=BatteryState.CHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_min_changed_pixels() == self.config.min_changed_pixels

    def test_get_min_changed_pixels_critical_battery(self) -> None:
        """Test min changed pixels when battery is critical."""
        battery_status = BatteryStatus(
            level=10,
            voltage=3.5,
            current=-300.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_min_changed_pixels() == self.config.min_changed_pixels_critical_battery

    def test_get_min_changed_pixels_low_battery(self) -> None:
        """Test min changed pixels when battery is low."""
        battery_status = BatteryStatus(
            level=20,
            voltage=3.6,
            current=-400.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_min_changed_pixels() == self.config.min_changed_pixels_low_battery

    def test_get_min_changed_pixels_normal_battery(self) -> None:
        """Test min changed pixels when battery is normal."""
        battery_status = BatteryStatus(
            level=75,
            voltage=3.8,
            current=-500.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_min_changed_pixels() == self.config.min_changed_pixels

    def test_edge_case_battery_at_boundaries(self) -> None:
        """Test thresholds at exact battery level boundaries."""
        # Test at exactly 10% (should be critical)
        battery_status = BatteryStatus(
            level=10,
            voltage=3.5,
            current=-300.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold_critical_battery
        assert self.manager.get_min_changed_pixels() == self.config.min_changed_pixels_critical_battery

        # Test at exactly 20% (should be low)
        battery_status = BatteryStatus(
            level=20,
            voltage=3.6,
            current=-400.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold_low_battery
        assert self.manager.get_min_changed_pixels() == self.config.min_changed_pixels_low_battery

        # Test at 21% (should be normal)
        battery_status = BatteryStatus(
            level=21,
            voltage=3.6,
            current=-400.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold
        assert self.manager.get_min_changed_pixels() == self.config.min_changed_pixels

    def test_should_use_battery_aware_thresholds(self) -> None:
        """Test internal method for determining battery aware usage."""
        # Initially should be False (no battery status)
        assert not self.manager._should_use_battery_aware_thresholds()

        # Set battery status
        battery_status = BatteryStatus(
            level=50,
            voltage=3.7,
            current=-450.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager._should_use_battery_aware_thresholds()

        # Disable battery aware in config
        self.manager.config.battery_aware_threshold = False
        assert not self.manager._should_use_battery_aware_thresholds()

    def test_get_pixel_diff_threshold_battery_aware_but_status_none(self) -> None:
        """Test pixel diff threshold when battery aware is enabled but status becomes None."""
        # First set a battery status
        battery_status = BatteryStatus(
            level=50,
            voltage=3.7,
            current=-450.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        
        # Then manually set the battery status to None (simulating battery monitor failure)
        self.manager._current_battery_status = None
        
        # Should return default threshold since battery status is None
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold
        

    def test_get_min_changed_pixels_battery_aware_but_status_none(self) -> None:
        """Test min changed pixels when battery aware is enabled but status becomes None."""
        # First set a battery status
        battery_status = BatteryStatus(
            level=50,
            voltage=3.7,
            current=-450.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        
        # Then manually set the battery status to None (simulating battery monitor failure)
        self.manager._current_battery_status = None
        
        # Should return default min changed pixels since battery status is None
        assert self.manager.get_min_changed_pixels() == self.config.min_changed_pixels
        

    def test_battery_state_not_charging_not_discharging(self) -> None:
        """Test thresholds when battery state is neither charging nor discharging."""
        # Test with FULL state
        battery_status = BatteryStatus(
            level=100,
            voltage=4.2,
            current=0.0,
            temperature=25.0,
            state=BatteryState.FULL,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold
        assert self.manager.get_min_changed_pixels() == self.config.min_changed_pixels

        # Test with UNKNOWN state
        battery_status = BatteryStatus(
            level=50,
            voltage=3.7,
            current=0.0,
            temperature=25.0,
            state=BatteryState.UNKNOWN,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold
        assert self.manager.get_min_changed_pixels() == self.config.min_changed_pixels

    def test_battery_levels_between_critical_and_low(self) -> None:
        """Test thresholds for battery levels between critical and low (11-19%)."""
        # Test at 11% (should be low, not critical)
        battery_status = BatteryStatus(
            level=11,
            voltage=3.5,
            current=-300.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold_low_battery
        assert self.manager.get_min_changed_pixels() == self.config.min_changed_pixels_low_battery

        # Test at 15% (should be low)
        battery_status = BatteryStatus(
            level=15,
            voltage=3.55,
            current=-350.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold_low_battery
        assert self.manager.get_min_changed_pixels() == self.config.min_changed_pixels_low_battery

        # Test at 19% (should be low)
        battery_status = BatteryStatus(
            level=19,
            voltage=3.59,
            current=-380.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold_low_battery
        assert self.manager.get_min_changed_pixels() == self.config.min_changed_pixels_low_battery

    def test_very_low_battery_levels(self) -> None:
        """Test thresholds for very low battery levels (below 10%)."""
        # Test at 5% (should be critical)
        battery_status = BatteryStatus(
            level=5,
            voltage=3.4,
            current=-250.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold_critical_battery
        assert self.manager.get_min_changed_pixels() == self.config.min_changed_pixels_critical_battery

        # Test at 1% (should be critical)
        battery_status = BatteryStatus(
            level=1,
            voltage=3.3,
            current=-200.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold_critical_battery
        assert self.manager.get_min_changed_pixels() == self.config.min_changed_pixels_critical_battery

    def test_multiple_state_transitions(self) -> None:
        """Test threshold changes as battery transitions through different states."""
        # Start with charging at 50%
        battery_status = BatteryStatus(
            level=50,
            voltage=3.7,
            current=1000.0,
            temperature=25.0,
            state=BatteryState.CHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold
        
        # Switch to discharging at 50%
        battery_status = BatteryStatus(
            level=50,
            voltage=3.7,
            current=-500.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold
        
        # Drop to low battery
        battery_status = BatteryStatus(
            level=20,
            voltage=3.6,
            current=-400.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold_low_battery
        
        # Drop to critical battery
        battery_status = BatteryStatus(
            level=10,
            voltage=3.5,
            current=-300.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold_critical_battery
        
        # Plug in charger at critical level
        battery_status = BatteryStatus(
            level=10,
            voltage=3.5,
            current=500.0,
            temperature=25.0,
            state=BatteryState.CHARGING,
        )
        self.manager.update_battery_status(battery_status)
        assert self.manager.get_pixel_diff_threshold() == self.config.pixel_diff_threshold

    def test_config_with_no_battery_aware_thresholds_defined(self) -> None:
        """Test behavior when battery-aware threshold config values are not explicitly set."""
        # Create config with minimal settings
        config = DisplayConfig(
            width=1872,
            height=1404,
            rotate=0,
            vcom=-2.06,
            refresh_interval_minutes=30,
            partial_refresh=True,
            timestamp_format="%Y-%m-%d %H:%M",
        )
        manager = BatteryThresholdManager(config)
        
        # Set a low battery status
        battery_status = BatteryStatus(
            level=10,
            voltage=3.5,
            current=-300.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        manager.update_battery_status(battery_status)
        
        # Should use default values from config model
        assert manager.get_pixel_diff_threshold() == config.pixel_diff_threshold_critical_battery
        assert manager.get_min_changed_pixels() == config.min_changed_pixels_critical_battery

    def test_type_checking_imports(self) -> None:
        """Test TYPE_CHECKING imports are covered."""
        # This test ensures TYPE_CHECKING blocks are covered
        with patch("typing.TYPE_CHECKING", True):
            # Re-import the module to trigger TYPE_CHECKING blocks
            if "rpi_weather_display.client.battery_threshold_manager" in sys.modules:
                del sys.modules["rpi_weather_display.client.battery_threshold_manager"]
            
            import rpi_weather_display.client.battery_threshold_manager
            
            # Verify the module imported successfully
            assert hasattr(rpi_weather_display.client.battery_threshold_manager, "BatteryThresholdManager")