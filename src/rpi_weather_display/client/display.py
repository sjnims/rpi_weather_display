"""E-paper display interface for the Raspberry Pi weather display.

Provides abstraction for interacting with the Waveshare e-paper display,
handling image rendering, partial refreshes, and power management.
"""
# ruff: noqa: S101, ANN401
# ^ Ignores "Use of assert detected" and "Any type" warnings

from pathlib import Path
from typing import Any, TypeVar

from PIL import Image

from rpi_weather_display.models.config import DisplayConfig

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
    """Interface for the Waveshare e-paper display."""

    def __init__(self, config: DisplayConfig) -> None:
        """Initialize the display driver.

        Args:
            config: Display configuration.
        """
        self.config = config
        self._display: Any | None = None
        self._last_image: Image.Image | None = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the e-paper display.

        This is separated from __init__ so that the display can be mocked for testing.
        """
        try:
            # Try to import the IT8951 library, which is only available on Raspberry Pi
            auto_epd_display = _import_it8951()
            if not auto_epd_display:
                print("Warning: IT8951 library not available. Using mock display.")
                self._initialized = False
                return

            # Initialize the display
            self._display = auto_epd_display(vcom=-2.06)
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
        """Check if the display is initialized."""
        if not self._initialized:
            raise RuntimeError("Display not initialized. Call initialize() first.")

    def clear(self) -> None:
        """Clear the display."""
        if self._initialized and self._display:
            self._display.clear()
            self._last_image = None

    def display_image(self, image_path: str | Path) -> None:
        """Display an image on the e-paper display.

        Args:
            image_path: Path to the image file.
        """
        image = Image.open(image_path)
        self.display_pil_image(image)

    def display_pil_image(self, image: Image.Image) -> None:
        """Display a PIL Image on the e-paper display.

        Args:
            image: PIL Image object.
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
        """Calculate the dimensions of the bounding box.

        Args:
            non_zero: Tuple of arrays with non-zero indices
            diff_shape: Shape of the difference array

        Returns:
            Bounding box as (left, top, right, bottom) or None
        """
        np = _import_numpy()
        if not np:
            return None

        left = max(0, int(np.min(non_zero[1])) - 5)  # Add margin
        top = max(0, int(np.min(non_zero[0])) - 5)
        right = min(int(diff_shape[1]), int(np.max(non_zero[1])) + 5)
        bottom = min(int(diff_shape[0]), int(np.max(non_zero[0])) + 5)

        return (left, top, right, bottom)

    def _calculate_diff_bbox(
        self, old_image: Image.Image, new_image: Image.Image
    ) -> tuple[int, int, int, int] | None:
        """Calculate the bounding box of differences between two images.

        Args:
            old_image: Previous image.
            new_image: New image.

        Returns:
            Tuple of (left, top, right, bottom) or None if no significant differences.
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

            # If max difference is below threshold, return None
            if np.max(diff) < 10:  # Threshold for considering a pixel changed
                return None

            # Find non-zero positions
            non_zero = np.where(diff > 10)

            # If no significant differences, return None
            if len(non_zero[0]) == 0:
                return None

            # Calculate and return bounding box
            return self._get_bbox_dimensions(non_zero, diff.shape)
        except Exception as e:
            print(f"Error calculating diff bbox: {e}")
            return None

    def sleep(self) -> None:
        """Put the display to sleep (deep sleep mode)."""
        if self._initialized and self._display and hasattr(self._display, "epd"):
            try:
                self._display.epd.sleep()
            except AttributeError:
                # If sleep not available, we'll just leave it as is
                pass

    def display_text(self, title: str, message: str) -> None:
        """Display a text message on the e-paper display.
        
        Creates a simple text image with the given title and message
        for displaying alerts or status messages.
        
        Args:
            title: The title/heading text to display
            message: The main message text to display
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # Create a blank white image
            image = Image.new("L", (self.config.width, self.config.height), 255)
            draw = ImageDraw.Draw(image)
            
            # Determine font sizes based on display size
            title_font_size = max(36, min(48, self.config.width // 20))
            message_font_size = max(24, min(36, self.config.width // 30))
            
            # Try to load a font, fall back to default if not available
            try:
                title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", title_font_size)
                message_font = ImageFont.truetype("DejaVuSans.ttf", message_font_size)
            except OSError:
                # Fall back to default font
                title_font = ImageFont.load_default()
                message_font = ImageFont.load_default()
            
            # Calculate positions
            title_bbox = draw.textbbox((0, 0), title, font=title_font)
            title_width = title_bbox[2] - title_bbox[0]
            title_x = (self.config.width - title_width) // 2
            title_y = self.config.height // 3
            
            message_bbox = draw.textbbox((0, 0), message, font=message_font)
            message_width = message_bbox[2] - message_bbox[0]
            message_x = (self.config.width - message_width) // 2
            message_y = self.config.height // 2
            
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
        """Close and clean up the display."""
        self.sleep()
        self._initialized = False
        self._display = None
