"""E-paper display interface for the Raspberry Pi weather display.

Provides abstraction for interacting with the Waveshare e-paper display,
handling image rendering, partial refreshes, and power management.
"""
# ruff: noqa: S101, ANN401
# ^ Ignores "Use of assert detected" and "Any type" warnings

from pathlib import Path
from typing import Any, TypeVar

from PIL import Image

from rpi_weather_display.constants import (
    DEFAULT_MESSAGE_FONT,
    DEFAULT_TITLE_FONT,
    DISPLAY_MARGIN,
    FONT_SIZE_DIVIDER,
    FONT_SIZE_MESSAGE_DIVIDER,
    MESSAGE_FONT_SIZE_BASE,
    MESSAGE_FONT_SIZE_MAX,
    MESSAGE_Y_POSITION_FACTOR,
    TITLE_FONT_SIZE_BASE,
    TITLE_FONT_SIZE_MAX,
    TITLE_Y_POSITION_FACTOR,
)
from rpi_weather_display.models.config import DisplayConfig
from rpi_weather_display.models.system import BatteryState, BatteryStatus

# Define type variables for conditional imports
AutoEPDDisplayType = TypeVar("AutoEPDDisplayType")

# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false


def _import_it8951() -> Any | None:
    """Import IT8951 library or return None if not available."""
    try:
        from IT8951.display import AutoEPDDisplay  # type: ignore

        return AutoEPDDisplay
    except ImportError:
        return None


def _import_numpy() -> Any | None:
    """Import numpy or return None if not available."""
    try:
        import numpy as np  # type: ignore

        return np
    except ImportError:
        return None


class EPaperDisplay:
    """Interface for the Waveshare e-paper display.

    This class provides a high-level interface for controlling the e-paper display,
    including image display, text rendering, power management, and partial refresh
    functionality with battery-aware optimizations.

    Attributes:
        config: Display configuration parameters
        _display: The underlying IT8951 display driver instance
        _last_image: Previously displayed image for partial refresh comparison
        _initialized: Whether the display has been successfully initialized
        _current_battery_status: Current battery status for power-aware refresh
    """

    def __init__(self, config: DisplayConfig) -> None:
        """Initialize the display driver.

        Args:
            config: Display configuration including dimensions, rotation, and refresh settings.
        """
        self.config = config
        self._display: Any | None = None
        self._last_image: Image.Image | None = None
        self._initialized = False
        self._current_battery_status: BatteryStatus | None = None

    def initialize(self) -> None:
        """Initialize the e-paper display hardware.

        This is separated from __init__ so that the display can be mocked for testing.
        Attempts to connect to the IT8951 display driver, clear the screen, and set
        the display rotation. If the IT8951 library is not available (e.g., when not
        running on Raspberry Pi hardware), a mock display is used instead.

        Raises:
            RuntimeError: If the display initialization fails.
        """
        try:
            # Try to import the IT8951 library, which is only available on Raspberry Pi
            auto_epd_display = _import_it8951()
            if not auto_epd_display:
                print("Warning: IT8951 library not available. Using mock display.")
                self._initialized = False
                return

            # Initialize the display with configured VCOM value
            self._display = auto_epd_display(vcom=self.config.vcom)
            if self._display:
                self._display.clear()

                # Set rotation
                if self.config.rotate in [0, 90, 180, 270]:
                    self._display.epd.set_rotation(self.config.rotate // 90)

            self._initialized = True
        except Exception as e:
            # Log any other exceptions
            print(f"Error initializing display: {e}")
            self._initialized = False

    def _check_initialized(self) -> None:
        """Check if the display is initialized.

        Raises:
            RuntimeError: If the display has not been initialized.
        """
        if not self._initialized:
            raise RuntimeError("Display not initialized. Call initialize() first.")

    def clear(self) -> None:
        """Clear the display.

        Clears the entire display to white and resets the last image cache.
        If the display is not initialized, this operation is silently skipped.
        """
        if self._initialized and self._display:
            self._display.clear()
            self._last_image = None

    def display_image(self, image_path: str | Path) -> None:
        """Display an image from a file on the e-paper display.

        Args:
            image_path: Path to the image file to display.

        Raises:
            FileNotFoundError: If the image file does not exist.
            PIL.UnidentifiedImageError: If the file is not a valid image.
        """
        image = Image.open(image_path)
        self.display_pil_image(image)

    def update_battery_status(self, battery_status: BatteryStatus) -> None:
        """Update the current battery status for dynamic adjustments.

        This information is used to modify refresh thresholds and behavior
        based on battery level, helping extend battery life when needed.

        Args:
            battery_status: The current battery status including level and charging state.
        """
        self._current_battery_status = battery_status

    def display_pil_image(self, image: Image.Image) -> None:
        """Display a PIL Image on the e-paper display.

        Handles image preprocessing (resizing, conversion to grayscale) and
        implements power-efficient partial refresh when appropriate based on
        battery status and configuration settings.

        Args:
            image: PIL Image object to display.

        Raises:
            Exception: If there is an error during image display.
        """
        if not self._initialized:
            print(f"Mock display: would display image of size {image.size}")
            self._last_image = image
            return

        try:
            # Resize image if necessary
            if image.size != (self.config.width, self.config.height):
                # Handle LANCZOS resampling which might have different names in different PIL
                # versions
                resampling = getattr(Image, "LANCZOS", getattr(Image, "ANTIALIAS", 1))
                image = image.resize((self.config.width, self.config.height), resampling)

            # Convert to grayscale if not already
            if image.mode != "L":
                image = image.convert("L")

            # Check if we can use partial refresh
            if self.config.partial_refresh and self._last_image is not None:
                # Calculate the bounding box of differences
                bbox = self._calculate_diff_bbox(self._last_image, image)

                # If there's a significant difference, update the display
                if bbox:
                    # Display the image with partial refresh
                    if self._display:
                        self._display.display_partial(image, bbox)
                else:
                    # No significant difference, no need to update
                    return
            else:
                # Full refresh
                if self._display:
                    self._display.display(image)

            # Save the current image for future partial refreshes
            self._last_image = image
        except Exception as e:
            print(f"Error displaying image: {e}")

    def _get_bbox_dimensions(
        self, non_zero: tuple[list[int], list[int]], diff_shape: tuple[int, int]
    ) -> tuple[int, int, int, int] | None:
        """Calculate the dimensions of the bounding box for partial refresh.

        Takes the non-zero pixel positions from the difference image and
        calculates a bounding box that contains all changed pixels, with
        a margin to ensure smooth updates.

        Args:
            non_zero: Tuple of arrays with non-zero pixel indices (rows, columns)
            diff_shape: Shape of the difference array (height, width)

        Returns:
            Bounding box as (left, top, right, bottom) or None if calculation fails
        """
        np = _import_numpy()
        if not np:
            return None

        left = max(0, int(np.min(non_zero[1])) - DISPLAY_MARGIN)  # Add margin
        top = max(0, int(np.min(non_zero[0])) - DISPLAY_MARGIN)
        right = min(int(diff_shape[1]), int(np.max(non_zero[1])) + DISPLAY_MARGIN)
        bottom = min(int(diff_shape[0]), int(np.max(non_zero[0])) + DISPLAY_MARGIN)

        return (left, top, right, bottom)

    def _calculate_diff_bbox(
        self, old_image: Image.Image, new_image: Image.Image
    ) -> tuple[int, int, int, int] | None:
        """Calculate the bounding box of differences between two images.

        Compares the previous and new images to determine which areas have changed
        significantly. Uses configurable thresholds that adapt based on battery status
        to optimize power usage.

        Args:
            old_image: Previously displayed image
            new_image: New image to be displayed

        Returns:
            Tuple of (left, top, right, bottom) defining the update region, or
            None if no significant differences exist or the calculation fails
        """
        try:
            np = _import_numpy()
            if not np:
                return None

            # Convert to numpy arrays
            old_array = np.array(old_image)
            new_array = np.array(new_image)

            # Calculate difference
            diff = np.abs(old_array.astype(np.int16) - new_array.astype(np.int16))

            # Get the appropriate threshold based on battery status
            pixel_threshold = self._get_pixel_diff_threshold()
            min_changed_pixels = self._get_min_changed_pixels()

            # If max difference is below threshold, return None
            if np.max(diff) < pixel_threshold:
                return None

            # Find non-zero positions
            non_zero = np.where(diff > pixel_threshold)

            # If insufficient pixels have changed, return None
            if len(non_zero[0]) < min_changed_pixels:
                return None

            # Calculate and return bounding box
            return self._get_bbox_dimensions(non_zero, diff.shape)
        except Exception as e:
            print(f"Error calculating diff bbox: {e}")
            return None

    def _get_pixel_diff_threshold(self) -> int:
        """Get the pixel difference threshold based on battery status.

        Implements battery-aware thresholds to reduce refresh frequency
        when battery is low, extending overall battery life.

        Returns:
            The threshold value to use for pixel differences
        """
        # If battery-aware thresholds are disabled, return the default threshold
        if not self.config.battery_aware_threshold or self._current_battery_status is None:
            return self.config.pixel_diff_threshold

        # Use appropriate threshold based on battery status
        battery = self._current_battery_status
        is_discharging = battery.state == BatteryState.DISCHARGING

        if battery.state == BatteryState.CHARGING:
            # When charging, use the standard threshold
            return self.config.pixel_diff_threshold
        elif battery.level <= 10 and is_discharging:
            # Critical battery (10% or less and discharging)
            return self.config.pixel_diff_threshold_critical_battery
        elif battery.level <= 20 and is_discharging:
            # Low battery (20% or less and discharging)
            return self.config.pixel_diff_threshold_low_battery
        else:
            # Normal battery or other states
            return self.config.pixel_diff_threshold

    def _get_min_changed_pixels(self) -> int:
        """Get the minimum number of changed pixels required based on battery status.

        Implements battery-aware thresholds to ensure refreshes only occur when
        there are enough changed pixels to warrant an update, which helps reduce
        power consumption when battery is low.

        Returns:
            The minimum number of changed pixels required to trigger a refresh
        """
        # If battery-aware thresholds are disabled, return the default threshold
        if not self.config.battery_aware_threshold or self._current_battery_status is None:
            return self.config.min_changed_pixels

        # Use appropriate threshold based on battery status
        battery = self._current_battery_status
        is_discharging = battery.state == BatteryState.DISCHARGING

        if battery.state == BatteryState.CHARGING:
            # When charging, use the standard threshold
            return self.config.min_changed_pixels
        elif battery.level <= 10 and is_discharging:
            # Critical battery (10% or less and discharging)
            return self.config.min_changed_pixels_critical_battery
        elif battery.level <= 20 and is_discharging:
            # Low battery (20% or less and discharging)
            return self.config.min_changed_pixels_low_battery
        else:
            # Normal battery or other states
            return self.config.min_changed_pixels

    def sleep(self) -> None:
        """Put the display to sleep (deep sleep mode) to conserve power.

        When in deep sleep mode, the display consumes minimal power but requires
        a full refresh when waking up again. This is useful for periods when
        the display will not be updated for a while.
        """
        if self._initialized and self._display and hasattr(self._display, "epd"):
            try:
                self._display.epd.sleep()
            except AttributeError:
                # If sleep not available, we'll just leave it as is
                pass

    def display_text(self, title: str, message: str) -> None:
        """Display a text message on the e-paper display.

        Creates a simple text image with the given title and message
        for displaying alerts or status messages. Handles font loading,
        text positioning, and rendering automatically.

        Args:
            title: The title/heading text to display at the top
            message: The main message text to display below the title

        Raises:
            Exception: If there is an error during text rendering or display
        """
        try:
            from PIL import Image, ImageDraw, ImageFont

            # Create a blank white image
            image = Image.new("L", (self.config.width, self.config.height), 255)
            draw = ImageDraw.Draw(image)

            # Determine font sizes based on display size
            title_font_size = max(
                TITLE_FONT_SIZE_BASE,
                min(TITLE_FONT_SIZE_MAX, self.config.width // FONT_SIZE_DIVIDER),
            )
            message_font_size = max(
                MESSAGE_FONT_SIZE_BASE,
                min(MESSAGE_FONT_SIZE_MAX, self.config.width // FONT_SIZE_MESSAGE_DIVIDER),
            )

            # Try to load a font, fall back to default if not available
            try:
                title_font = ImageFont.truetype(DEFAULT_TITLE_FONT, title_font_size)
                message_font = ImageFont.truetype(DEFAULT_MESSAGE_FONT, message_font_size)
            except OSError:
                # Fall back to default font
                title_font = ImageFont.load_default()
                message_font = ImageFont.load_default()

            # Calculate positions
            title_bbox = draw.textbbox((0, 0), title, font=title_font)
            title_width = title_bbox[2] - title_bbox[0]
            title_x = (self.config.width - title_width) // 2
            title_y = self.config.height // TITLE_Y_POSITION_FACTOR

            message_bbox = draw.textbbox((0, 0), message, font=message_font)
            message_width = message_bbox[2] - message_bbox[0]
            message_x = (self.config.width - message_width) // 2
            message_y = self.config.height // MESSAGE_Y_POSITION_FACTOR

            # Draw the text
            draw.text((title_x, title_y), title, font=title_font, fill=0)
            draw.text((message_x, message_y), message, font=message_font, fill=0)

            # Display the image
            self.display_pil_image(image)

        except Exception as e:
            print(f"Error displaying text: {e}")
            # If we can't create a proper image, at least log the message
            print(f"Message: {title} - {message}")

    def close(self) -> None:
        """Close and clean up the display resources.

        Puts the display into sleep mode and releases any resources.
        Should be called when the application is shutting down.
        """
        self.sleep()
        self._initialized = False
        self._display = None