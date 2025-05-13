"""E-paper display interface for the Raspberry Pi weather display.

Provides abstraction for interacting with the Waveshare e-paper display,
handling image rendering, partial refreshes, and power management.
"""

from pathlib import Path
from typing import Any, TypeVar

from PIL import Image

from rpi_weather_display.models.config import DisplayConfig

# Define type variables for conditional imports
AutoEPDDisplayType = TypeVar("AutoEPDDisplayType")

# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false


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
            from IT8951.display import AutoEPDDisplay  # type: ignore

            # Initialize the display
            self._display = AutoEPDDisplay(vcom=-2.06)
            self._display.clear()

            # Set rotation
            if self.config.rotate in [0, 90, 180, 270]:
                self._display.epd.set_rotation(self.config.rotate // 90)

            self._initialized = True
        except ImportError:
            # When running on development machine, print message
            print("Warning: IT8951 library not available. Using mock display.")
            self._initialized = False
        except Exception as e:
            # Log any other exceptions
            print(f"Error initializing display: {e}")
            self._initialized = False

    def _check_initialized(self) -> None:
        """Check if the display is initialized."""
        if not self._initialized and not self._display:
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
            import numpy as np  # type: ignore

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

            # Calculate bounding box
            left = max(0, int(np.min(non_zero[1])) - 5)  # Add margin
            top = max(0, int(np.min(non_zero[0])) - 5)
            right = min(int(diff.shape[1]), int(np.max(non_zero[1])) + 5)
            bottom = min(int(diff.shape[0]), int(np.max(non_zero[0])) + 5)

            return (left, top, right, bottom)
        except ImportError:
            # numpy not available, return None
            return None
        except Exception as e:
            print(f"Error calculating diff bbox: {e}")
            return None

    def sleep(self) -> None:
        """Put the display to sleep (deep sleep mode)."""
        if self._initialized and self._display:
            # Some e-paper displays have a sleep command
            try:
                self._display.epd.sleep()
            except AttributeError:
                # If sleep not available, we'll just leave it as is
                pass

    def close(self) -> None:
        """Close and clean up the display."""
        self.sleep()
        self._initialized = False
        self._display = None
