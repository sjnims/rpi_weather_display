"""Partial refresh management for e-paper displays.

Coordinates partial refresh operations to minimize power consumption
by only updating changed regions of the display.
"""

from typing import TYPE_CHECKING, Protocol

from PIL import Image

from rpi_weather_display.exceptions import (
    DisplayUpdateError,
    PartialRefreshError,
    chain_exception,
)

if TYPE_CHECKING:
    from rpi_weather_display.client.battery_threshold_manager import BatteryThresholdManager
    from rpi_weather_display.client.image_processor import ImageProcessor
    from rpi_weather_display.models.config import DisplayConfig


class DisplayProtocol(Protocol):
    """Protocol for display interface used by partial refresh manager."""
    
    def display(self, img: Image.Image) -> None:
        """Display full image."""
        pass
        
    def display_partial(
        self, img: Image.Image, bbox: tuple[int, int, int, int] | None = None
    ) -> None:
        """Display partial image update."""
        pass


class PartialRefreshManager:
    """Manages partial refresh operations for e-paper displays.
    
    This class coordinates the logic for determining when and how to use
    partial refresh, optimizing power consumption by only updating changed
    regions when appropriate.
    
    Attributes:
        config: Display configuration
        image_processor: Image processing utilities
        battery_threshold_manager: Battery-aware threshold management
        _last_image: Previously displayed image for comparison
    """
    
    def __init__(
        self,
        config: "DisplayConfig",
        image_processor: "ImageProcessor",
        battery_threshold_manager: "BatteryThresholdManager"
    ) -> None:
        """Initialize the partial refresh manager.
        
        Args:
            config: Display configuration
            image_processor: Image processor instance
            battery_threshold_manager: Battery threshold manager instance
        """
        self.config = config
        self.image_processor = image_processor
        self.battery_threshold_manager = battery_threshold_manager
        self._last_image: Image.Image | None = None
        
    def update_display(
        self,
        new_image: Image.Image,
        display: DisplayProtocol | None
    ) -> bool:
        """Update display with appropriate refresh strategy.
        
        Determines whether to use partial or full refresh based on
        configuration and image differences.
        
        Args:
            new_image: New image to display
            display: Display interface or None for mock mode
            
        Returns:
            True if display was updated, False if no update needed
            
        Raises:
            DisplayUpdateError: If display update fails
            PartialRefreshError: If partial refresh operation fails
        """
        try:
            if not display:
                self._update_last_image(new_image)
                return True
                
            if self.config.partial_refresh and self._last_image is not None:
                updated = self._handle_partial_refresh(new_image, display)
            else:
                updated = self._handle_full_refresh(new_image, display)
                
            if updated:
                self._update_last_image(new_image)
                
            return updated
            
        except (DisplayUpdateError, PartialRefreshError):
            # Re-raise display-specific exceptions as-is
            raise
        except Exception as e:
            # Wrap other errors in DisplayUpdateError
            raise chain_exception(
                DisplayUpdateError(
                    "Failed to update display",
                    {
                        "partial_refresh_enabled": self.config.partial_refresh,
                        "has_last_image": self._last_image is not None,
                        "error": str(e)
                    }
                ),
                e
            ) from None
        
    def _handle_partial_refresh(
        self,
        new_image: Image.Image,
        display: DisplayProtocol
    ) -> bool:
        """Handle partial refresh logic.
        
        Args:
            new_image: New image to display
            display: Display interface
            
        Returns:
            True if display was updated, False if no update needed
            
        Raises:
            PartialRefreshError: If partial refresh operation fails
        """
        if self._last_image is None:
            return self._handle_full_refresh(new_image, display)
            
        # Initialize variables for error handling
        pixel_threshold = None
        min_changed_pixels = None
        bbox = None
            
        try:
            # Get thresholds from battery manager
            pixel_threshold = self.battery_threshold_manager.get_pixel_diff_threshold()
            min_changed_pixels = self.battery_threshold_manager.get_min_changed_pixels()
            
            # Calculate changed region
            bbox = self.image_processor.calculate_diff_bbox(
                self._last_image,
                new_image,
                pixel_threshold,
                min_changed_pixels
            )
            
            if bbox:
                display.display_partial(new_image, bbox)
                return True
                
            # No significant changes
            return False
            
        except Exception as e:
            raise chain_exception(
                PartialRefreshError(
                    "Failed to perform partial refresh",
                    {
                        "pixel_threshold": pixel_threshold,
                        "min_changed_pixels": min_changed_pixels,
                        "bbox": bbox,
                        "error": str(e)
                    }
                ),
                e
            ) from None
        
    def _handle_full_refresh(
        self,
        new_image: Image.Image,
        display: DisplayProtocol
    ) -> bool:
        """Handle full refresh logic.
        
        Args:
            new_image: New image to display
            display: Display interface
            
        Returns:
            True (full refresh always updates)
            
        Raises:
            DisplayUpdateError: If full refresh fails
        """
        try:
            display.display(new_image)
            return True
        except Exception as e:
            raise chain_exception(
                DisplayUpdateError(
                    "Failed to perform full refresh",
                    {
                        "image_size": new_image.size,
                        "image_mode": new_image.mode,
                        "error": str(e)
                    }
                ),
                e
            ) from None
        
    def _update_last_image(self, new_image: Image.Image) -> None:
        """Update the stored last image reference.
        
        Args:
            new_image: New image to store
        """
        # Clean up old image
        if self._last_image is not None:
            self._last_image.close()
            
        # Store new image
        self._last_image = new_image
        
    def clear_last_image(self) -> None:
        """Clear the stored last image."""
        if self._last_image is not None:
            self._last_image.close()
            self._last_image = None