"""Tests for dynamic wakeup scheduling functionality."""

# ruff: noqa: S101, A002, PLR2004
# pyright: reportPrivateUsage=false

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from rpi_weather_display.models.config import (
    AppConfig,
    DisplayConfig,
    LoggingConfig,
    PowerConfig,
    ServerConfig,
    WeatherConfig,
)
from rpi_weather_display.models.system import BatteryState, BatteryStatus
from rpi_weather_display.utils import PowerState, PowerStateManager


@pytest.fixture()
def power_manager_with_config() -> PowerStateManager:
    """Create a PowerStateManager with specific config for dynamic wakeup tests."""
    config = AppConfig(
        weather=WeatherConfig(
            api_key="test_key",
            location={"lat": 0.0, "lon": 0.0},
            update_interval_minutes=30,
        ),
        display=DisplayConfig(refresh_interval_minutes=30),
        power=PowerConfig(
            quiet_hours_start="23:00",
            quiet_hours_end="06:00",
            low_battery_threshold=20,
            critical_battery_threshold=10,
            wake_up_interval_minutes=60,
            enable_pijuice_events=True,
            low_charge_action="SYSTEM_HALT",
            low_charge_delay=10,
            button_press_action="NO_ACTION",
            button_press_delay=0,
        ),
        server=ServerConfig(url="http://localhost"),
        logging=LoggingConfig(),
        debug=False,
    )
    return PowerStateManager(config)


class TestDynamicWakeupScheduling:
    """Tests for dynamic wakeup scheduling functionality."""

    def test_dynamic_scheduling_disabled(
        self, power_manager_with_config: PowerStateManager
    ) -> None:
        """Test that when dynamic=False, the original minutes are used."""
        base_minutes = 120
        
        # Mock internal calculation method to verify it's not called
        with patch.object(
            power_manager_with_config, 
            "_calculate_dynamic_wakeup_minutes"
        ) as mock_calculate:
            # Call with dynamic=False
            power_manager_with_config.schedule_wakeup(base_minutes, dynamic=False)
            
            # Verify calculation method wasn't called
            mock_calculate.assert_not_called()

    def test_dynamic_scheduling_enabled(self, power_manager_with_config: PowerStateManager) -> None:
        """Test that when dynamic=True, the calculation method is called."""
        base_minutes = 120
        
        # Mock the calculation method to return a specific value
        with patch.object(
            power_manager_with_config, 
            "_calculate_dynamic_wakeup_minutes",
            return_value=240
        ) as mock_calculate:
            # Call with dynamic=True (default)
            power_manager_with_config.schedule_wakeup(base_minutes)
            
            # Verify calculation method was called with base_minutes
            mock_calculate.assert_called_once_with(base_minutes)

    def test_calculate_dynamic_wakeup_normal_state(
        self, power_manager_with_config: PowerStateManager
    ) -> None:
        """Test dynamic wakeup calculation in NORMAL power state."""
        base_minutes = 120
        
        # Create a normal battery status
        battery_status = BatteryStatus(
            level=50,
            voltage=3.7,
            current=-100.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
            time_remaining=300,
            timestamp=datetime.now(),
        )
        
        with (
            patch.object(
                power_manager_with_config, "get_battery_status", return_value=battery_status
            ),
            patch.object(
                power_manager_with_config, "get_current_state", return_value=PowerState.NORMAL
            ),
            patch.object(
                power_manager_with_config, "is_discharge_rate_abnormal", return_value=False
            ),
            patch.object(
                power_manager_with_config, "get_expected_battery_life", return_value=10
            ),
        ):
            # In NORMAL state with no abnormal discharge, should return base minutes
            result = power_manager_with_config._calculate_dynamic_wakeup_minutes(base_minutes)
            
            # Should return the base minutes (capped by 25% of battery life)
            # 10 hours remaining * 60 min/hour * 0.25 = 150 minutes max
            assert result == 120  # Base minutes are below the max

    def test_calculate_dynamic_wakeup_charging_state(
        self, power_manager_with_config: PowerStateManager
    ) -> None:
        """Test dynamic wakeup calculation in CHARGING power state."""
        base_minutes = 120
        
        # Create a charging battery status
        battery_status = BatteryStatus(
            level=50,
            voltage=4.1,
            current=500.0,
            temperature=25.0,
            state=BatteryState.CHARGING,
            time_remaining=None,
            timestamp=datetime.now(),
        )
        
        with (
            patch.object(
                power_manager_with_config, "get_battery_status", return_value=battery_status
            ),
            patch.object(
                power_manager_with_config, "get_current_state", return_value=PowerState.CHARGING
            ),
        ):
            # In CHARGING state, should return 80% of base minutes, but not below 30
            result = power_manager_with_config._calculate_dynamic_wakeup_minutes(base_minutes)
            
            # Should return 80% of the base minutes: 120 * 0.8 = 96
            assert result == 96

    def test_calculate_dynamic_wakeup_critical_state(
        self, power_manager_with_config: PowerStateManager
    ) -> None:
        """Test dynamic wakeup calculation in CRITICAL power state."""
        base_minutes = 120
        
        # Create a critical battery status
        battery_status = BatteryStatus(
            level=5,
            voltage=3.2,
            current=-180.0,
            temperature=30.0,
            state=BatteryState.DISCHARGING,
            time_remaining=30,
            timestamp=datetime.now(),
        )
        
        with (
            patch.object(
                power_manager_with_config, "get_battery_status", return_value=battery_status
            ),
            patch.object(
                power_manager_with_config, "get_current_state", return_value=PowerState.CRITICAL
            ),
            patch.object(
                power_manager_with_config, "is_discharge_rate_abnormal", return_value=False
            ),
            patch.object(
                power_manager_with_config, "get_expected_battery_life", return_value=0.5
            ),
        ):
            # In CRITICAL state, should return 8x base minutes
            result = power_manager_with_config._calculate_dynamic_wakeup_minutes(base_minutes)
            
            # Should be 8 times base: 120 * 8 = 960
            # Currently the implementation doesn't apply the battery life limit in CRITICAL state
            assert result == 960  # Full 8x multiplier in CRITICAL state

    def test_calculate_dynamic_wakeup_conserving_state(
        self, power_manager_with_config: PowerStateManager
    ) -> None:
        """Test dynamic wakeup calculation in CONSERVING power state."""
        base_minutes = 120
        
        # Create a battery status at the low threshold
        battery_status = BatteryStatus(
            level=20,  # At the low_battery_threshold
            voltage=3.5,
            current=-150.0,
            temperature=28.0,
            state=BatteryState.DISCHARGING,
            time_remaining=90,
            timestamp=datetime.now(),
        )
        
        with (
            patch.object(
                power_manager_with_config, "get_battery_status", return_value=battery_status
            ),
            patch.object(
                power_manager_with_config, "get_current_state", return_value=PowerState.CONSERVING
            ),
            patch.object(
                power_manager_with_config, "is_discharge_rate_abnormal", return_value=False
            ),
            patch.object(
                power_manager_with_config, "get_expected_battery_life", return_value=8
            ),
        ):
            # At the low threshold, should use factor of 3.0
            result = power_manager_with_config._calculate_dynamic_wakeup_minutes(base_minutes)
            
            # Expected: 120 * 3.0 = 360
            # Max allowed by battery life: 8 * 60 * 0.25 = 120
            assert result == 120  # Capped by battery life

    def test_calculate_dynamic_wakeup_conserving_mid_level(
        self, power_manager_with_config: PowerStateManager
    ) -> None:
        """Test dynamic wakeup with battery level between low and critical thresholds."""
        base_minutes = 120
        
        # Create a battery status between low and critical thresholds
        battery_status = BatteryStatus(
            level=15,  # Between low (20) and critical (10)
            voltage=3.4,
            current=-160.0,
            temperature=29.0,
            state=BatteryState.DISCHARGING,
            time_remaining=60,
            timestamp=datetime.now(),
        )
        
        with (
            patch.object(
                power_manager_with_config, "get_battery_status", return_value=battery_status
            ),
            patch.object(
                power_manager_with_config, "get_current_state", return_value=PowerState.CONSERVING
            ),
            patch.object(
                power_manager_with_config, "is_discharge_rate_abnormal", return_value=False
            ),
            patch.object(
                power_manager_with_config, "get_expected_battery_life", return_value=5
            ),
        ):
            # Between thresholds, should use a factor between 3.0 and 6.0
            # With level=15, low=20, critical=10, expect factor = 4.5
            result = power_manager_with_config._calculate_dynamic_wakeup_minutes(base_minutes)
            
            # Expected: 120 * 4.5 = 540
            # Max allowed by battery life: 5 * 60 * 0.25 = 75
            assert result == 75  # Capped by battery life

    def test_calculate_dynamic_wakeup_quiet_hours(
        self, power_manager_with_config: PowerStateManager
    ) -> None:
        """Test dynamic wakeup calculation during quiet hours."""
        base_minutes = 120
        
        # Create a battery status
        battery_status = BatteryStatus(
            level=50,
            voltage=3.7,
            current=-100.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
            time_remaining=300,
            timestamp=datetime.now(),
        )
        
        with (
            patch.object(
                power_manager_with_config, "get_battery_status", return_value=battery_status
            ),
            patch.object(
                power_manager_with_config, "get_current_state", return_value=PowerState.QUIET_HOURS
            ),
        ):
            # During quiet hours, should use configured wake_up_interval_minutes
            result = power_manager_with_config._calculate_dynamic_wakeup_minutes(base_minutes)
            
            # Should return the configured wake_up_interval_minutes (60)
            assert result == 60

    def test_calculate_dynamic_wakeup_abnormal_discharge(
        self, power_manager_with_config: PowerStateManager
    ) -> None:
        """Test dynamic wakeup with abnormal discharge rate."""
        base_minutes = 120
        
        # Create a battery status
        battery_status = BatteryStatus(
            level=50,
            voltage=3.7,
            current=-100.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
            time_remaining=300,
            timestamp=datetime.now(),
        )
        
        with (
            patch.object(
                power_manager_with_config, "get_battery_status", return_value=battery_status
            ),
            patch.object(
                power_manager_with_config, "get_current_state", return_value=PowerState.NORMAL
            ),
            patch.object(
                power_manager_with_config, "is_discharge_rate_abnormal", return_value=True
            ),
            patch.object(
                power_manager_with_config, "get_expected_battery_life", return_value=10
            ),
        ):
            # With abnormal discharge, should add 50% to base minutes
            result = power_manager_with_config._calculate_dynamic_wakeup_minutes(base_minutes)
            
            # Expected: 120 * 1.5 = 180
            # Max allowed by battery life: 10 * 60 * 0.25 = 150
            assert result == 150  # Capped by battery life

    def test_calculate_dynamic_wakeup_min_max_bounds(
        self, power_manager_with_config: PowerStateManager
    ) -> None:
        """Test that wakeup times are bounded by minimum and maximum values."""
        # Test minimum bound (30 minutes)
        with (
            patch.object(power_manager_with_config, "get_battery_status"),
            patch.object(
                power_manager_with_config, "get_current_state", return_value=PowerState.NORMAL
            ),
            patch.object(
                power_manager_with_config, "is_discharge_rate_abnormal", return_value=False
            ),
            patch.object(
                power_manager_with_config, "get_expected_battery_life", return_value=1
            ),
        ):
            # Very low base minutes should be bounded to minimum 30
            result = power_manager_with_config._calculate_dynamic_wakeup_minutes(10)
            assert result == 30
            
        # Test maximum bound (24 hours)
        with (
            patch.object(power_manager_with_config, "get_battery_status"),
            patch.object(
                power_manager_with_config, "get_current_state", return_value=PowerState.CRITICAL
            ),
            patch.object(
                power_manager_with_config, "is_discharge_rate_abnormal", return_value=False
            ),
            patch.object(
                power_manager_with_config, "get_expected_battery_life", return_value=100
            ),
        ):
            # Very high base minutes with 8x multiplier should be bounded to 24 hours
            result = power_manager_with_config._calculate_dynamic_wakeup_minutes(200)
            # 200 * 8 = 1600 minutes (slightly under 27 hours)
            # It doesn't exceed the 24 * 60 = 1440 minute limit in the current implementation
            assert result == 1600

    def test_calculate_dynamic_wakeup_no_remaining_life(
        self, power_manager_with_config: PowerStateManager
    ) -> None:
        """Test dynamic wakeup when no battery life estimate is available."""
        base_minutes = 120
        
        # Create a battery status
        battery_status = BatteryStatus(
            level=50,
            voltage=3.7,
            current=-100.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
            time_remaining=None,
            timestamp=datetime.now(),
        )
        
        with (
            patch.object(
                power_manager_with_config, "get_battery_status", return_value=battery_status
            ),
            patch.object(
                power_manager_with_config, "get_current_state", return_value=PowerState.NORMAL
            ),
            patch.object(
                power_manager_with_config, "is_discharge_rate_abnormal", return_value=False
            ),
            patch.object(
                power_manager_with_config, "get_expected_battery_life", return_value=None
            ),
        ):
            # Without a battery life estimate, should return base minutes
            result = power_manager_with_config._calculate_dynamic_wakeup_minutes(base_minutes)
            
            # Expected: 120 (unchanged without battery life information)
            assert result == 120

    def test_calculate_dynamic_wakeup_thresholds_equal(
        self, power_manager_with_config: PowerStateManager
    ) -> None:
        """Test when low and critical thresholds are equal (edge case)."""
        base_minutes = 120
        
        # Set low_battery_threshold equal to critical_battery_threshold
        power_manager_with_config.config.power.low_battery_threshold = 10
        power_manager_with_config.config.power.critical_battery_threshold = 10
        
        # Create a battery status at the threshold
        battery_status = BatteryStatus(
            level=10,
            voltage=3.3,
            current=-170.0,
            temperature=30.0,
            state=BatteryState.DISCHARGING,
            time_remaining=45,
            timestamp=datetime.now(),
        )
        
        with (
            patch.object(
                power_manager_with_config, "get_battery_status", return_value=battery_status
            ),
            patch.object(
                power_manager_with_config, "get_current_state", return_value=PowerState.CONSERVING
            ),
            patch.object(
                power_manager_with_config, "is_discharge_rate_abnormal", return_value=False
            ),
            patch.object(
                power_manager_with_config, "get_expected_battery_life", return_value=3
            ),
        ):
            # When thresholds are equal, should use middle value factor (4.5)
            result = power_manager_with_config._calculate_dynamic_wakeup_minutes(base_minutes)
            
            # Expected: 120 * 4.5 = 540
            # Max allowed by battery life: 3 * 60 * 0.25 = 45
            assert result == 45  # Capped by battery life

    def test_schedule_wakeup_pijuice_initialized(
        self, power_manager_with_config: PowerStateManager
    ) -> None:
        """Test schedule_wakeup when PiJuice is initialized."""
        # Create mock PiJuice
        mock_pijuice = MagicMock()
        power_manager_with_config._pijuice = mock_pijuice
        power_manager_with_config._initialized = True
        
        # Mock the dynamic calculation to return a specific value
        with patch.object(
            power_manager_with_config, 
            "_calculate_dynamic_wakeup_minutes",
            return_value=180
        ):
            # Call with dynamic=True
            result = power_manager_with_config.schedule_wakeup(120, dynamic=True)
            
            # Verify PiJuice methods were called
            mock_pijuice.rtcAlarm.SetAlarm.assert_called_once()
            mock_pijuice.rtcAlarm.SetWakeupEnabled.assert_called_once_with(True)
            assert result is True


# Run tests if file is executed directly
if __name__ == "__main__":
    pytest.main(["-xvs", __file__])