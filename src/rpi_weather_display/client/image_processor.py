"""Image processing utilities for e-paper display.

Handles image preprocessing, format conversion, and difference calculations
for efficient display updates.
"""

from types import ModuleType
from typing import TYPE_CHECKING

from PIL import Image

from rpi_weather_display.constants import DISPLAY_MARGIN

if TYPE_CHECKING:
    from rpi_weather_display.models.config import DisplayConfig


def _import_numpy() -> ModuleType | None:
    """Import numpy or return None if not available.
    
    Returns:
        The numpy module if available, or None if the library cannot be imported
    """
    try:
        import numpy as np
        return np
    except ImportError:
        return None


class ImageProcessor:
    """Handles image processing operations for e-paper display.
    
    This class encapsulates image preprocessing, format conversion,
    and difference calculations needed for efficient display updates.
    
    Attributes:
        config: Display configuration with dimensions
    """
    
    def __init__(self, config: "DisplayConfig") -> None:
        """Initialize the image processor.
        
        Args:
            config: Display configuration containing dimensions
        """
        self.config = config
        
    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocess image for e-paper display.
        
        Resizes image to display dimensions and converts to grayscale
        as required by e-paper displays.
        
        Args:
            image: Original PIL Image object
            
        Returns:
            Processed PIL Image ready for display
        """
        processed_image = image
        
        # Resize if necessary
        if image.size != (self.config.width, self.config.height):
            # Handle different PIL versions
            resampling = getattr(Image, "LANCZOS", getattr(Image, "ANTIALIAS", 1))
            processed_image = image.resize(
                (self.config.width, self.config.height), 
                resampling
            )
            
        # Convert to grayscale
        if processed_image.mode != "L":
            processed_image = processed_image.convert("L")
            
        return processed_image
        
    def calculate_diff_bbox(
        self, 
        old_image: Image.Image, 
        new_image: Image.Image,
        pixel_threshold: int,
        min_changed_pixels: int
    ) -> tuple[int, int, int, int] | None:
        """Calculate bounding box of differences between two images.
        
        Compares images to determine which areas have changed significantly,
        enabling partial refresh optimization.
        
        Args:
            old_image: Previously displayed image
            new_image: New image to be displayed
            pixel_threshold: Minimum pixel difference to consider changed
            min_changed_pixels: Minimum total changed pixels for update
            
        Returns:
            Bounding box (left, top, right, bottom) or None if no significant changes
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
            
            # Check if max difference exceeds threshold
            max_diff = np.max(diff)
            if max_diff < pixel_threshold:
                del old_array, new_array, diff
                return None
                
            # Find changed pixels
            non_zero = np.where(diff > pixel_threshold)
            
            # Check if enough pixels changed
            if len(non_zero[0]) < min_changed_pixels:
                del old_array, new_array, diff
                return None
                
            # Calculate bounding box
            bbox = self._calculate_bbox_dimensions(non_zero, diff.shape, np)
            
            # Clean up
            del old_array, new_array, diff
            
            return bbox
            
        except Exception as e:
            print(f"Error calculating diff bbox: {e}")
            return None
            
    def _calculate_bbox_dimensions(
        self, 
        non_zero: tuple[list[int], list[int]], 
        diff_shape: tuple[int, int],
        np: ModuleType
    ) -> tuple[int, int, int, int] | None:
        """Calculate bounding box dimensions with margin.
        
        Args:
            non_zero: Tuple of arrays with non-zero pixel indices (rows, columns)
            diff_shape: Shape of the difference array (height, width)
            np: NumPy module
            
        Returns:
            Bounding box (left, top, right, bottom) or None
        """
        try:
            left = max(0, int(np.min(non_zero[1])) - DISPLAY_MARGIN)
            top = max(0, int(np.min(non_zero[0])) - DISPLAY_MARGIN)
            right = min(int(diff_shape[1]), int(np.max(non_zero[1])) + DISPLAY_MARGIN)
            bottom = min(int(diff_shape[0]), int(np.max(non_zero[0])) + DISPLAY_MARGIN)
            
            return (left, top, right, bottom)
        except Exception:
            return None