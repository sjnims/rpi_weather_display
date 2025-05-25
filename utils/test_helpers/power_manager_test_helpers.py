"""Test helper utilities for power management components.

This module provides test-only helper methods that were previously embedded
in production code. These helpers allow tests to access and modify internal
state for testing purposes without polluting the production interfaces.
"""

# pyright: reportPrivateUsage=false

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rpi_weather_display.utils.power_manager import PowerStateManager
    from rpi_weather_display.utils.power_state_controller import PowerState, PowerStateController


class PowerStateControllerTestHelper:
    """Test helper for PowerStateController internal state access."""

    @staticmethod
    def get_internal_state(controller: "PowerStateController") -> "PowerState":
        """Get internal state for testing.
        
        Args:
            controller: PowerStateController instance
            
        Returns:
            Current internal power state
        """
        return controller._current_state

    @staticmethod
    def set_internal_state(controller: "PowerStateController", state: "PowerState") -> None:
        """Set internal state for testing.
        
        Args:
            controller: PowerStateController instance
            state: Power state to set
        """
        controller._current_state = state

    @staticmethod
    def get_last_refresh(controller: "PowerStateController") -> datetime | None:
        """Get last refresh time for testing.
        
        Args:
            controller: PowerStateController instance
            
        Returns:
            Last display refresh timestamp or None
        """
        return controller._last_display_refresh

    @staticmethod
    def set_last_refresh(controller: "PowerStateController", time: datetime | None) -> None:
        """Set last refresh time for testing.
        
        Args:
            controller: PowerStateController instance
            time: Timestamp to set
        """
        controller._last_display_refresh = time

    @staticmethod
    def get_last_update(controller: "PowerStateController") -> datetime | None:
        """Get last update time for testing.
        
        Args:
            controller: PowerStateController instance
            
        Returns:
            Last weather update timestamp or None
        """
        return controller._last_weather_update

    @staticmethod
    def set_last_update(controller: "PowerStateController", time: datetime | None) -> None:
        """Set last update time for testing.
        
        Args:
            controller: PowerStateController instance
            time: Timestamp to set
        """
        controller._last_weather_update = time


class PowerStateManagerTestHelper:
    """Test helper for PowerStateManager internal state access."""

    @staticmethod
    def get_internal_state(manager: "PowerStateManager") -> "PowerState":
        """Get internal state for testing.
        
        Args:
            manager: PowerStateManager instance
            
        Returns:
            Current internal power state from the controller
        """
        if manager._power_controller:
            return PowerStateControllerTestHelper.get_internal_state(manager._power_controller)
        from rpi_weather_display.utils.power_state_controller import PowerState
        return PowerState.NORMAL

    @staticmethod
    def set_internal_state(manager: "PowerStateManager", state: "PowerState") -> None:
        """Set internal state for testing.
        
        Args:
            manager: PowerStateManager instance
            state: Power state to set
        """
        if manager._power_controller:
            PowerStateControllerTestHelper.set_internal_state(manager._power_controller, state)

    @staticmethod
    def get_initialization_status(manager: "PowerStateManager") -> bool:
        """Get initialization status for testing.
        
        Args:
            manager: PowerStateManager instance
            
        Returns:
            True if manager is initialized
        """
        return manager._initialized

    @staticmethod
    def get_last_refresh(manager: "PowerStateManager") -> datetime | None:
        """Get last refresh time for testing.
        
        Args:
            manager: PowerStateManager instance
            
        Returns:
            Last display refresh timestamp or None
        """
        if manager._power_controller:
            return PowerStateControllerTestHelper.get_last_refresh(manager._power_controller)
        return None

    @staticmethod
    def set_last_refresh(manager: "PowerStateManager", time: datetime | None) -> None:
        """Set last refresh time for testing.
        
        Args:
            manager: PowerStateManager instance
            time: Timestamp to set
        """
        if manager._power_controller:
            PowerStateControllerTestHelper.set_last_refresh(manager._power_controller, time)

    @staticmethod
    def get_last_update(manager: "PowerStateManager") -> datetime | None:
        """Get last update time for testing.
        
        Args:
            manager: PowerStateManager instance
            
        Returns:
            Last weather update timestamp or None
        """
        if manager._power_controller:
            return PowerStateControllerTestHelper.get_last_update(manager._power_controller)
        return None

    @staticmethod
    def set_last_update(manager: "PowerStateManager", time: datetime | None) -> None:
        """Set last update time for testing.
        
        Args:
            manager: PowerStateManager instance
            time: Timestamp to set
        """
        if manager._power_controller:
            PowerStateControllerTestHelper.set_last_update(manager._power_controller, time)
