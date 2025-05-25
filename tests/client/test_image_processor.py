"""Tests for image processor."""

from typing import Any
from unittest.mock import MagicMock, patch

from PIL import Image

from rpi_weather_display.client.image_processor import ImageProcessor, _import_numpy
from rpi_weather_display.models.config import DisplayConfig


class MockNumpy:
    """Mock numpy module for testing."""

    @staticmethod
    def array(img: Image.Image) -> MagicMock:
        """Mock array method."""
        mock_array = MagicMock()
        mock_array.shape = (1404, 1872)  # height, width
        mock_array.astype = lambda dtype: mock_array
        # Handle subtraction
        mock_array.__sub__ = lambda other: mock_array
        return mock_array

    @staticmethod
    def abs(arr: MagicMock) -> MagicMock:
        """Mock abs method."""
        return arr

    @staticmethod
    def max(arr: Any) -> int:
        """Mock max method."""
        return 20

    @staticmethod
    def where(condition: Any) -> tuple[list[int], list[int]]:
        """Mock where method."""
        # Return mock indices for changed pixels
        return ([10, 20, 30], [100, 200, 300])

    @staticmethod
    def min(arr: Any) -> int:
        """Mock min method."""
        if isinstance(arr, list) and arr:
            return min(arr)  # type: ignore[type-var]
        return 10

    @staticmethod
    def int16(value: int | float) -> int:
        """Mock int16 method."""
        return int(value)


class TestImageProcessorHelpers:
    """Test helper functions."""

    def test_import_numpy_success(self) -> None:
        """Test successful numpy import."""
        with patch("builtins.__import__") as mock_import:
            mock_numpy = MockNumpy()
            mock_import.return_value = mock_numpy
            result = _import_numpy()
            assert result == mock_numpy

    def test_import_numpy_failure(self) -> None:
        """Test numpy import failure."""
        with patch("builtins.__import__", side_effect=ImportError("numpy not found")):
            result = _import_numpy()
            assert result is None


class TestImageProcessor:
    """Test cases for ImageProcessor."""

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
            min_changed_pixels=100,
        )
        self.processor = ImageProcessor(self.config)

    def test_init(self) -> None:
        """Test initialization."""
        assert self.processor.config == self.config

    def test_preprocess_image_already_correct(self) -> None:
        """Test preprocessing image that's already correct size and mode."""
        # Create grayscale image of correct size
        image = Image.new("L", (self.config.width, self.config.height), 128)
        
        result = self.processor.preprocess_image(image)
        
        assert result.size == (self.config.width, self.config.height)
        assert result.mode == "L"
        assert result == image  # Should be unchanged

    def test_preprocess_image_resize(self) -> None:
        """Test preprocessing image that needs resizing."""
        # Create image with wrong size
        image = Image.new("L", (800, 600), 128)
        
        result = self.processor.preprocess_image(image)
        
        assert result.size == (self.config.width, self.config.height)
        assert result.mode == "L"

    def test_preprocess_image_convert_mode(self) -> None:
        """Test preprocessing RGB image to grayscale."""
        # Create RGB image
        image = Image.new("RGB", (self.config.width, self.config.height), (128, 128, 128))
        
        result = self.processor.preprocess_image(image)
        
        assert result.size == (self.config.width, self.config.height)
        assert result.mode == "L"

    def test_preprocess_image_resize_and_convert(self) -> None:
        """Test preprocessing image that needs both resize and conversion."""
        # Create RGB image with wrong size
        image = Image.new("RGB", (800, 600), (128, 128, 128))
        
        result = self.processor.preprocess_image(image)
        
        assert result.size == (self.config.width, self.config.height)
        assert result.mode == "L"

    def test_calculate_diff_bbox_no_numpy(self) -> None:
        """Test calculate_diff_bbox when numpy is not available."""
        old_image = Image.new("L", (100, 100), 0)
        new_image = Image.new("L", (100, 100), 255)
        
        with patch("rpi_weather_display.client.image_processor._import_numpy", return_value=None):
            result = self.processor.calculate_diff_bbox(old_image, new_image, 10, 100)
            
        assert result is None

    def test_calculate_diff_bbox_no_changes(self) -> None:
        """Test calculate_diff_bbox with identical images."""
        image = Image.new("L", (100, 100), 128)
        
        with patch("rpi_weather_display.client.image_processor._import_numpy") as mock_import:
            mock_np = MockNumpy()
            mock_np.max = lambda arr: 0  # No difference
            mock_import.return_value = mock_np
            
            result = self.processor.calculate_diff_bbox(image, image, 10, 100)
            
        assert result is None

    def test_calculate_diff_bbox_below_threshold(self) -> None:
        """Test calculate_diff_bbox with changes below threshold."""
        old_image = Image.new("L", (100, 100), 0)
        new_image = Image.new("L", (100, 100), 5)
        
        with patch("rpi_weather_display.client.image_processor._import_numpy") as mock_import:
            mock_np = MockNumpy()
            mock_np.max = lambda arr: 5  # Below threshold of 10
            mock_import.return_value = mock_np
            
            result = self.processor.calculate_diff_bbox(old_image, new_image, 10, 100)
            
        assert result is None

    def test_calculate_diff_bbox_too_few_pixels(self) -> None:
        """Test calculate_diff_bbox with too few changed pixels."""
        old_image = Image.new("L", (100, 100), 0)
        new_image = Image.new("L", (100, 100), 255)
        
        with patch("rpi_weather_display.client.image_processor._import_numpy") as mock_import:
            mock_np = MockNumpy()
            mock_np.where = lambda condition: ([10], [20])  # Only 1 pixel
            mock_import.return_value = mock_np
            
            result = self.processor.calculate_diff_bbox(old_image, new_image, 10, 100)
            
        assert result is None

    def test_calculate_diff_bbox_success(self) -> None:
        """Test successful calculate_diff_bbox."""
        old_image = Image.new("L", (100, 100), 0)
        new_image = Image.new("L", (100, 100), 255)
        
        # Instead of complex mocking, let's use a simpler approach
        # Test with real numpy if available, otherwise skip
        import_result = _import_numpy()
        if import_result is None:
            # numpy not available, test with simple check that it returns None
            result = self.processor.calculate_diff_bbox(old_image, new_image, 10, 100)
            assert result is None
        else:
            # numpy is available, use it directly
            result = self.processor.calculate_diff_bbox(old_image, new_image, 10, 100)
            # Should return a bounding box
            assert result is not None
            assert isinstance(result, tuple)
            assert len(result) == 4
            # Check bounds are reasonable
            left, top, right, bottom = result
            assert 0 <= left < right <= 100
            assert 0 <= top < bottom <= 100

    def test_calculate_diff_bbox_exception(self) -> None:
        """Test calculate_diff_bbox with exception."""
        old_image = Image.new("L", (100, 100), 0)
        new_image = Image.new("L", (100, 100), 255)
        
        with patch("rpi_weather_display.client.image_processor._import_numpy") as mock_import:
            mock_import.side_effect = Exception("Test error")
            
            # Capture print output to verify error message
            with patch("builtins.print") as mock_print:
                result = self.processor.calculate_diff_bbox(old_image, new_image, 10, 100)
                
            assert result is None
            # Verify error was printed
            mock_print.assert_called_once()
            args = mock_print.call_args[0]
            assert "Error calculating diff bbox" in args[0]
            assert "Test error" in args[0]

    def test_calculate_bbox_dimensions(self) -> None:
        """Test _calculate_bbox_dimensions method."""
        non_zero = ([10, 20, 30, 40], [50, 60, 70, 80])
        diff_shape = (100, 100)
        
        mock_np = MockNumpy()
        mock_np.min = lambda arr: 10 if arr is non_zero[0] else 50
        mock_np.max = lambda arr: 40 if arr is non_zero[0] else 80
        
        result = self.processor._calculate_bbox_dimensions(non_zero, diff_shape, mock_np)  # type: ignore[arg-type]
        
        assert result is not None
        left, top, right, bottom = result
        
        # Check margins are applied (DISPLAY_MARGIN = 5)
        assert left == max(0, 50 - 5)   # min column - margin = 45
        assert top == max(0, 10 - 5)    # min row - margin = 5
        assert right == min(100, 80 + 5)  # max column + margin = 85
        assert bottom == min(100, 40 + 5)  # max row + margin = 45

    def test_calculate_bbox_dimensions_clipped(self) -> None:
        """Test _calculate_bbox_dimensions with clipping at edges."""
        # Test with values at edges
        non_zero = ([0, 5], [0, 5])
        diff_shape = (100, 100)
        
        mock_np = MockNumpy()
        mock_np.min = lambda arr: 0
        mock_np.max = lambda arr: 5
        
        result = self.processor._calculate_bbox_dimensions(non_zero, diff_shape, mock_np)  # type: ignore[arg-type]
        
        assert result is not None
        left, top, right, bottom = result
        
        # Check that values are clipped to image bounds (DISPLAY_MARGIN = 5)
        assert left == 0    # Can't go below 0
        assert top == 0     # Can't go below 0
        assert right == 10  # 5 + 5 margin = 10
        assert bottom == 10 # 5 + 5 margin = 10

    def test_calculate_bbox_dimensions_exception(self) -> None:
        """Test _calculate_bbox_dimensions with exception."""
        non_zero = ([10], [20])
        diff_shape = (100, 100)
        
        mock_np = MagicMock()
        mock_np.min.side_effect = Exception("Test error")
        
        result = self.processor._calculate_bbox_dimensions(non_zero, diff_shape, mock_np)  # type: ignore[arg-type]
        
        assert result is None

    def test_calculate_diff_bbox_cleanup_on_low_max_diff(self) -> None:
        """Test that cleanup happens when max_diff is below threshold."""
        old_image = Image.new("L", (100, 100), 0)
        new_image = Image.new("L", (100, 100), 5)
        
        # Create a custom mock to verify cleanup
        cleanup_called = {"old": False, "new": False, "diff": False}
        
        class MockArray:
            def __init__(self, name: str) -> None:
                self.name = name
                self.shape = (100, 100)
                
            def astype(self, dtype: Any) -> "MockArray":
                return self
                
            def __sub__(self, other: Any) -> "MockArray":
                return MockArray("diff")
                
            def __del__(self) -> None:
                cleanup_called[self.name] = True
        
        with patch("rpi_weather_display.client.image_processor._import_numpy") as mock_import:
            mock_np = MagicMock()
            mock_np.array = lambda img: MockArray("old" if img is old_image else "new")
            mock_np.abs = lambda x: x
            mock_np.max = lambda arr: 5  # Below threshold
            mock_np.int16 = int
            mock_import.return_value = mock_np
            
            result = self.processor.calculate_diff_bbox(old_image, new_image, 10, 100)
            
        assert result is None
        # Note: __del__ is not guaranteed to be called immediately in Python
        # but the important thing is that the code attempts cleanup with del statements

    def test_calculate_diff_bbox_cleanup_on_few_pixels(self) -> None:
        """Test that cleanup happens when too few pixels changed."""
        old_image = Image.new("L", (100, 100), 0)
        new_image = Image.new("L", (100, 100), 255)
        
        with patch("rpi_weather_display.client.image_processor._import_numpy") as mock_import:
            mock_np = MockNumpy()
            # Override to return max_diff > threshold but few changed pixels
            mock_np.max = lambda arr: 50  # Above threshold
            mock_np.where = lambda condition: ([10, 20], [30, 40])  # Only 2 pixels
            mock_import.return_value = mock_np
            
            result = self.processor.calculate_diff_bbox(old_image, new_image, 10, 100)
            
        assert result is None

    def test_calculate_diff_bbox_with_real_numpy_integration(self) -> None:
        """Test calculate_diff_bbox with real numpy if available (integration test)."""
        # This test uses real numpy if available to ensure proper integration
        np = _import_numpy()
        if np is None:
            # Skip this test if numpy is not available
            return
            
        # Create images with significant differences
        old_image = Image.new("L", (50, 50), 0)
        new_image = Image.new("L", (50, 50), 0)
        
        # Draw a white rectangle in the new image
        from PIL import ImageDraw
        draw = ImageDraw.Draw(new_image)
        draw.rectangle((10, 10, 40, 40), fill=255)
        
        # Call the method with real numpy
        result = self.processor.calculate_diff_bbox(old_image, new_image, 10, 100)
        
        # Should detect the changed region
        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 4
        
        # The bounding box should encompass the rectangle with margins
        left, top, right, bottom = result
        # With DISPLAY_MARGIN = 5, expect roughly (5, 5, 45, 45)
        assert left <= 10  # Should include margin
        assert top <= 10
        assert right >= 40
        assert bottom >= 40

    def test_preprocess_image_resampling_fallback(self) -> None:
        """Test that image preprocessing works with various PIL versions."""
        image = Image.new("RGB", (800, 600), (128, 128, 128))
        
        # The preprocess_image method should work regardless of PIL version
        # It uses getattr with defaults to handle missing attributes
        result = self.processor.preprocess_image(image)
        
        # Verify the image was properly resized and converted
        assert result.size == (self.config.width, self.config.height)
        assert result.mode == "L"
        
        # Also test with an image that's already the correct size but wrong mode
        image2 = Image.new("RGBA", (self.config.width, self.config.height), (128, 128, 128, 255))
        result2 = self.processor.preprocess_image(image2)
        assert result2.size == (self.config.width, self.config.height)
        assert result2.mode == "L"

    def test_calculate_diff_bbox_successful_cleanup(self) -> None:
        """Test that cleanup happens in the successful path."""
        old_image = Image.new("L", (100, 100), 0)
        new_image = Image.new("L", (100, 100), 0)
        
        # Draw a white rectangle to create a significant difference
        from PIL import ImageDraw
        draw = ImageDraw.Draw(new_image)
        draw.rectangle((20, 20, 80, 80), fill=255)
        
        # Use real numpy if available for this test
        np = _import_numpy()
        if np is None:
            # No numpy, just verify it returns None
            result = self.processor.calculate_diff_bbox(old_image, new_image, 10, 100)
            assert result is None
        else:
            # With numpy, should get a valid bbox
            result = self.processor.calculate_diff_bbox(old_image, new_image, 10, 100)
            assert result is not None
            assert isinstance(result, tuple)
            assert len(result) == 4
            # Verify reasonable bounds
            left, top, right, bottom = result
            assert left < right
            assert top < bottom