"""E-paper display interface for the Raspberry Pi weather display.

Provides abstraction for interacting with the Waveshare e-paper display,
handling image rendering, partial refreshes, and power management.
"""

# ruff: noqa: S101
# ^ Ignores "Use of assert detected" warnings

# pyright: reportUnknownVariableType=false
# pyright: reportUnknownMemberType=false

import logging
from collections.abc import Callable
from io import BytesIO
from typing import TYPE_CHECKING, Protocol, TypeVar

from PIL import Image

from rpi_weather_display.client.battery_threshold_manager import BatteryThresholdManager
from rpi_weather_display.client.image_processor import ImageProcessor
from rpi_weather_display.client.partial_refresh_manager import PartialRefreshManager
from rpi_weather_display.client.text_renderer import TextRenderer
from rpi_weather_display.constants import VALID_ROTATION_ANGLES
from rpi_weather_display.exceptions import (
    DisplayError,
    DisplayInitializationError,
    DisplayUpdateError,
    chain_exception,
)
from rpi_weather_display.models.config import DisplayConfig
from rpi_weather_display.models.system import BatteryStatus
from rpi_weather_display.utils.file_utils import PathLike, read_bytes

# Type checking imports
if TYPE_CHECKING:
    pass


# Define protocol for EPD display interface
class EPDProtocol(Protocol):
    """Protocol for low-level e-paper display driver."""

    def set_rotation(self, rotation: int) -> None:
        """Set display rotation."""
        pass

    def sleep(self) -> None:
        """Put display to sleep."""
        pass


class EPDDisplayProtocol(Protocol):
    """Protocol for e-paper display interface."""

    width: int
    height: int
    epd: EPDProtocol

    def display(self, img: Image.Image) -> None:
        """Display an image."""
        pass

    def display_partial(
        self, img: Image.Image, bbox: tuple[int, int, int, int] | None = None
    ) -> None:
        """Display partial image update."""
        pass

    def clear(self) -> None:
        """Clear the display."""
        pass

    def sleep(self) -> None:
        """Put display to sleep."""
        pass


# Define type variables for conditional imports
AutoEPDDisplayType = TypeVar("AutoEPDDisplayType", bound=EPDDisplayProtocol)


def _import_it8951() -> Callable[..., EPDDisplayProtocol] | None:
    """Import IT8951 library or return None if not available.

    Returns:
        The AutoEPDDisplay class or None if unavailable
    """
    try:
        from IT8951.display import AutoEPDDisplay  # type: ignore

        return AutoEPDDisplay
    except ImportError:
        return None


class EPaperDisplay:
    """Interface for the Waveshare e-paper display.

    This class provides a high-level interface for controlling the e-paper display,
    coordinating between various specialized components for optimal functionality.

    Attributes:
        config: Display configuration parameters
        battery_threshold_manager: Manages battery-aware thresholds
        image_processor: Handles image preprocessing
        partial_refresh_manager: Manages partial refresh operations
        text_renderer: Handles text rendering
        _display: The underlying IT8951 display driver instance
        _initialized: Whether the display has been successfully initialized
    """

    def __init__(self, config: DisplayConfig) -> None:
        """Initialize the display driver.

        Args:
            config: Display configuration including dimensions and settings
        """
        self.config = config
        self._display: EPDDisplayProtocol | None = None
        self._initialized = False
        self.logger = logging.getLogger(__name__)
        
        # Initialize component managers
        self.battery_threshold_manager = BatteryThresholdManager(config)
        self.image_processor = ImageProcessor(config)
        self.partial_refresh_manager = PartialRefreshManager(
            config, 
            self.image_processor,
            self.battery_threshold_manager
        )
        self.text_renderer = TextRenderer(config)

    def initialize(self) -> None:
        """Initialize the e-paper display hardware.

        Attempts to connect to the IT8951 display driver and configure it.
        Falls back to mock mode if hardware is not available.
        
        Raises:
            DisplayInitializationError: If display hardware initialization fails
        """
        try:
            auto_epd_display = _import_it8951()
            if not auto_epd_display:
                self.logger.warning("IT8951 library not available. Using mock display.")
                self._initialized = False
                return

            # Initialize display
            self._display = auto_epd_display(vcom=self.config.vcom)
            if self._display:
                self._display.clear()
                self._set_rotation()

            self._initialized = True
        except Exception as e:
            self._initialized = False
            raise chain_exception(
                DisplayInitializationError(
                    "Failed to initialize e-paper display",
                    {"vcom": self.config.vcom, "error": str(e)}
                ),
                e
            ) from None

    def _set_rotation(self) -> None:
        """Set display rotation if configured.
        
        Raises:
            DisplayError: If setting rotation fails
        """
        if (
            self._display 
            and self.config.rotate in VALID_ROTATION_ANGLES
            and hasattr(self._display, "epd")
        ):
            try:
                self._display.epd.set_rotation(self.config.rotate // 90)
            except Exception as e:
                raise chain_exception(
                    DisplayError(
                        f"Failed to set display rotation to {self.config.rotate} degrees",
                        {"rotation": self.config.rotate, "error": str(e)}
                    ),
                    e
                ) from None

    def clear(self) -> None:
        """Clear the display and reset state."""
        if self._initialized and self._display:
            self._display.clear()
        self.partial_refresh_manager.clear_last_image()

    def display_image(self, image_path: PathLike) -> None:
        """Display an image from file.

        Args:
            image_path: Path to the image file
        """
        image_data = read_bytes(image_path)
        with Image.open(BytesIO(image_data)) as image:
            self.display_pil_image(image)

    def display_pil_image(self, image: Image.Image) -> None:
        """Display a PIL Image on the e-paper display.

        Args:
            image: PIL Image object to display
            
        Raises:
            DisplayUpdateError: If displaying the image fails
        """
        if not self._initialized:
            self._handle_mock_display(image)
            return

        try:
            # Process image
            processed_image = self.image_processor.preprocess_image(image)
            
            # Update display through partial refresh manager
            updated = self.partial_refresh_manager.update_display(
                processed_image,
                self._display
            )
            
            # Clean up if image wasn't used
            if not updated and processed_image is not image:
                processed_image.close()
                
        except Exception as e:
            raise chain_exception(
                DisplayUpdateError(
                    "Failed to display image on e-paper display",
                    {"image_size": image.size, "mode": image.mode, "error": str(e)}
                ),
                e
            ) from None

    def _handle_mock_display(self, image: Image.Image) -> None:
        """Handle display operations in mock mode.
        
        Args:
            image: Image that would be displayed
        """
        self.logger.info(f"Mock display: would display image of size {image.size}")
        # Update partial refresh manager's state
        processed = self.image_processor.preprocess_image(image)
        self.partial_refresh_manager.update_display(processed, None)

    def display_text(self, title: str, message: str) -> None:
        """Display a text message on the display.

        Args:
            title: Title text
            message: Main message text
            
        Raises:
            DisplayUpdateError: If displaying the text fails
        """
        try:
            # Generate text image
            image = self.text_renderer.render_text_image(title, message)
            
            # Display it
            self.display_pil_image(image)
            
        except DisplayUpdateError:
            # Re-raise display update errors as-is
            raise
        except Exception as e:
            # Wrap other errors (like text rendering errors) in DisplayUpdateError
            raise chain_exception(
                DisplayUpdateError(
                    "Failed to display text on e-paper display",
                    {"title": title, "message": message, "error": str(e)}
                ),
                e
            ) from None

    def update_battery_status(self, battery_status: BatteryStatus) -> None:
        """Update battery status for threshold management.

        Args:
            battery_status: Current battery status
        """
        self.battery_threshold_manager.update_battery_status(battery_status)

    def sleep(self) -> None:
        """Put the display into deep sleep mode.
        
        Raises:
            DisplayError: If putting display to sleep fails
        """
        if self._initialized and self._display and hasattr(self._display, "epd"):
            try:
                self._display.epd.sleep()
            except Exception as e:
                if not isinstance(e, AttributeError):
                    raise chain_exception(
                        DisplayError(
                            "Failed to put display to sleep",
                            {"error": str(e)}
                        ),
                        e
                    ) from None

    def close(self) -> None:
        """Close and clean up display resources."""
        self.sleep()
        self.partial_refresh_manager.clear_last_image()
        self._initialized = False
        self._display = None