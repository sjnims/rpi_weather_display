"""Tests for partial refresh manager."""

from unittest.mock import MagicMock, create_autospec

from PIL import Image

from rpi_weather_display.client.battery_threshold_manager import BatteryThresholdManager
from rpi_weather_display.client.image_processor import ImageProcessor
from rpi_weather_display.client.partial_refresh_manager import (
    DisplayProtocol,
    PartialRefreshManager,
)
from rpi_weather_display.models.config import DisplayConfig


class TestPartialRefreshManager:
    """Test cases for PartialRefreshManager."""

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
        
        # Create mock dependencies
        self.mock_image_processor = create_autospec(ImageProcessor, instance=True)
        self.mock_battery_manager = create_autospec(BatteryThresholdManager, instance=True)
        
        # Set up default return values for battery manager
        self.mock_battery_manager.get_pixel_diff_threshold.return_value = 10
        self.mock_battery_manager.get_min_changed_pixels.return_value = 100
        
        self.manager = PartialRefreshManager(
            self.config,
            self.mock_image_processor,
            self.mock_battery_manager
        )

    def test_init(self) -> None:
        """Test initialization."""
        assert self.manager.config == self.config
        assert self.manager.image_processor == self.mock_image_processor
        assert self.manager.battery_threshold_manager == self.mock_battery_manager
        assert self.manager._last_image is None

    def test_update_display_no_display(self) -> None:
        """Test update_display with no display (mock mode)."""
        image = Image.new("L", (100, 100), 128)
        
        result = self.manager.update_display(image, None)
        
        assert result is True
        assert self.manager._last_image == image

    def test_update_display_first_image_full_refresh(self) -> None:
        """Test first image always uses full refresh."""
        image = Image.new("L", (100, 100), 128)
        mock_display = create_autospec(DisplayProtocol, instance=True)
        
        result = self.manager.update_display(image, mock_display)
        
        assert result is True
        mock_display.display.assert_called_once_with(image)
        mock_display.display_partial.assert_not_called()
        assert self.manager._last_image == image

    def test_update_display_partial_refresh_disabled(self) -> None:
        """Test update_display when partial refresh is disabled."""
        self.config.partial_refresh = False
        manager = PartialRefreshManager(
            self.config,
            self.mock_image_processor,
            self.mock_battery_manager
        )
        
        image = Image.new("L", (100, 100), 128)
        mock_display = create_autospec(DisplayProtocol, instance=True)
        
        result = manager.update_display(image, mock_display)
        
        assert result is True
        mock_display.display.assert_called_once_with(image)
        mock_display.display_partial.assert_not_called()

    def test_update_display_partial_refresh_with_changes(self) -> None:
        """Test partial refresh when changes are detected."""
        # Set up initial image
        first_image = Image.new("L", (100, 100), 128)
        second_image = Image.new("L", (100, 100), 200)
        mock_display = create_autospec(DisplayProtocol, instance=True)
        
        # Display first image
        self.manager.update_display(first_image, mock_display)
        
        # Configure mock to return a bounding box
        bbox = (10, 20, 90, 80)
        self.mock_image_processor.calculate_diff_bbox.return_value = bbox
        
        # Display second image
        mock_display.reset_mock()
        result = self.manager.update_display(second_image, mock_display)
        
        assert result is True
        mock_display.display_partial.assert_called_once_with(second_image, bbox)
        mock_display.display.assert_not_called()
        
        # Verify battery thresholds were used
        self.mock_battery_manager.get_pixel_diff_threshold.assert_called()
        self.mock_battery_manager.get_min_changed_pixels.assert_called()
        
        # Verify diff calculation
        self.mock_image_processor.calculate_diff_bbox.assert_called_once_with(
            first_image, second_image, 10, 100
        )

    def test_update_display_partial_refresh_no_changes(self) -> None:
        """Test partial refresh when no changes are detected."""
        # Set up initial image
        first_image = Image.new("L", (100, 100), 128)
        second_image = Image.new("L", (100, 100), 128)
        mock_display = create_autospec(DisplayProtocol, instance=True)
        
        # Display first image
        self.manager.update_display(first_image, mock_display)
        
        # Configure mock to return None (no changes)
        self.mock_image_processor.calculate_diff_bbox.return_value = None
        
        # Display second image
        mock_display.reset_mock()
        result = self.manager.update_display(second_image, mock_display)
        
        assert result is False
        mock_display.display_partial.assert_not_called()
        mock_display.display.assert_not_called()
        
        # Last image should not be updated
        assert self.manager._last_image == first_image

    def test_handle_partial_refresh_no_last_image(self) -> None:
        """Test _handle_partial_refresh with no last image."""
        image = Image.new("L", (100, 100), 128)
        mock_display = create_autospec(DisplayProtocol, instance=True)
        
        result = self.manager._handle_partial_refresh(image, mock_display)
        
        assert result is True
        mock_display.display.assert_called_once_with(image)
        mock_display.display_partial.assert_not_called()

    def test_handle_full_refresh(self) -> None:
        """Test _handle_full_refresh."""
        image = Image.new("L", (100, 100), 128)
        mock_display = create_autospec(DisplayProtocol, instance=True)
        
        result = self.manager._handle_full_refresh(image, mock_display)
        
        assert result is True
        mock_display.display.assert_called_once_with(image)

    def test_update_last_image(self) -> None:
        """Test _update_last_image."""
        # Create mock images with close method
        old_image = MagicMock(spec=Image.Image)
        new_image = MagicMock(spec=Image.Image)
        
        # Set initial image
        self.manager._last_image = old_image
        
        # Update to new image
        self.manager._update_last_image(new_image)
        
        # Verify old image was closed
        old_image.close.assert_called_once()
        assert self.manager._last_image == new_image

    def test_update_last_image_no_previous(self) -> None:
        """Test _update_last_image with no previous image."""
        image = MagicMock(spec=Image.Image)
        
        self.manager._update_last_image(image)
        
        assert self.manager._last_image == image

    def test_clear_last_image(self) -> None:
        """Test clear_last_image."""
        # Create mock image with close method
        image = MagicMock(spec=Image.Image)
        self.manager._last_image = image
        
        self.manager.clear_last_image()
        
        image.close.assert_called_once()
        assert self.manager._last_image is None

    def test_clear_last_image_already_none(self) -> None:
        """Test clear_last_image when already None."""
        self.manager._last_image = None
        
        # Should not raise any exception
        self.manager.clear_last_image()
        
        assert self.manager._last_image is None

    def test_battery_aware_thresholds(self) -> None:
        """Test that battery-aware thresholds are properly used."""
        # Set up different threshold values
        self.mock_battery_manager.get_pixel_diff_threshold.return_value = 20
        self.mock_battery_manager.get_min_changed_pixels.return_value = 200
        
        first_image = Image.new("L", (100, 100), 128)
        second_image = Image.new("L", (100, 100), 200)
        mock_display = create_autospec(DisplayProtocol, instance=True)
        
        # Display first image
        self.manager.update_display(first_image, mock_display)
        
        # Configure mock to return a bounding box
        bbox = (10, 20, 90, 80)
        self.mock_image_processor.calculate_diff_bbox.return_value = bbox
        
        # Display second image
        self.manager.update_display(second_image, mock_display)
        
        # Verify correct threshold values were used
        self.mock_image_processor.calculate_diff_bbox.assert_called_once_with(
            first_image, second_image, 20, 200
        )

    def test_display_protocol_implementation(self) -> None:
        """Test that DisplayProtocol can be properly implemented."""
        # Create a concrete implementation of DisplayProtocol
        class ConcreteDisplay:
            def __init__(self) -> None:
                self.full_display_calls: list[Image.Image] = []
                self.partial_display_calls: list[tuple[Image.Image, tuple[int, int, int, int] | None]] = []
            
            def display(self, img: Image.Image) -> None:
                self.full_display_calls.append(img)
            
            def display_partial(
                self, img: Image.Image, bbox: tuple[int, int, int, int] | None = None
            ) -> None:
                self.partial_display_calls.append((img, bbox))
        
        # Use the concrete implementation
        display = ConcreteDisplay()
        image = Image.new("L", (100, 100), 128)
        
        # Test full display
        result = self.manager.update_display(image, display)
        assert result is True
        assert len(display.full_display_calls) == 1
        assert display.full_display_calls[0] == image
        
        # Test partial display
        new_image = Image.new("L", (100, 100), 200)
        bbox = (10, 20, 90, 80)
        self.mock_image_processor.calculate_diff_bbox.return_value = bbox
        
        result = self.manager.update_display(new_image, display)
        assert result is True
        assert len(display.partial_display_calls) == 1
        assert display.partial_display_calls[0] == (new_image, bbox)

    def test_multiple_sequential_updates(self) -> None:
        """Test multiple sequential display updates."""
        mock_display = create_autospec(DisplayProtocol, instance=True)
        
        # First update - full refresh
        image1 = Image.new("L", (100, 100), 50)
        result1 = self.manager.update_display(image1, mock_display)
        assert result1 is True
        mock_display.display.assert_called_once()
        
        # Second update - partial refresh with changes
        image2 = Image.new("L", (100, 100), 100)
        bbox = (20, 20, 80, 80)
        self.mock_image_processor.calculate_diff_bbox.return_value = bbox
        mock_display.reset_mock()
        
        result2 = self.manager.update_display(image2, mock_display)
        assert result2 is True
        mock_display.display_partial.assert_called_once_with(image2, bbox)
        
        # Third update - no changes
        image3 = Image.new("L", (100, 100), 100)
        self.mock_image_processor.calculate_diff_bbox.return_value = None
        mock_display.reset_mock()
        
        result3 = self.manager.update_display(image3, mock_display)
        assert result3 is False
        mock_display.display.assert_not_called()
        mock_display.display_partial.assert_not_called()
        
        # Fourth update - changes detected again
        image4 = Image.new("L", (100, 100), 150)
        bbox2 = (30, 30, 70, 70)
        self.mock_image_processor.calculate_diff_bbox.return_value = bbox2
        mock_display.reset_mock()
        
        result4 = self.manager.update_display(image4, mock_display)
        assert result4 is True
        mock_display.display_partial.assert_called_once_with(image4, bbox2)

    def test_partial_refresh_with_none_bbox(self) -> None:
        """Test partial refresh when bbox calculation returns None."""
        # This is already covered in test_update_display_partial_refresh_no_changes
        # but let's add an explicit test for clarity
        first_image = Image.new("L", (100, 100), 128)
        mock_display = create_autospec(DisplayProtocol, instance=True)
        
        # Display first image
        self.manager.update_display(first_image, mock_display)
        assert self.manager._last_image == first_image
        
        # Try to display similar image
        similar_image = Image.new("L", (100, 100), 130)  # Very similar
        self.mock_image_processor.calculate_diff_bbox.return_value = None
        mock_display.reset_mock()
        
        result = self.manager.update_display(similar_image, mock_display)
        
        # Should not update
        assert result is False
        mock_display.display.assert_not_called()
        mock_display.display_partial.assert_not_called()
        # Last image should remain the same
        assert self.manager._last_image == first_image

    def test_edge_case_zero_thresholds(self) -> None:
        """Test behavior with zero thresholds from battery manager."""
        # Set zero thresholds
        self.mock_battery_manager.get_pixel_diff_threshold.return_value = 0
        self.mock_battery_manager.get_min_changed_pixels.return_value = 0
        
        first_image = Image.new("L", (100, 100), 128)
        second_image = Image.new("L", (100, 100), 129)  # Minimal change
        mock_display = create_autospec(DisplayProtocol, instance=True)
        
        # Display first image
        self.manager.update_display(first_image, mock_display)
        
        # Configure mock to return a bounding box (even for minimal changes)
        bbox = (0, 0, 100, 100)
        self.mock_image_processor.calculate_diff_bbox.return_value = bbox
        
        # Display second image
        mock_display.reset_mock()
        result = self.manager.update_display(second_image, mock_display)
        
        assert result is True
        mock_display.display_partial.assert_called_once_with(second_image, bbox)
        
        # Verify zero thresholds were passed
        self.mock_image_processor.calculate_diff_bbox.assert_called_once_with(
            first_image, second_image, 0, 0
        )

    def test_display_protocol_methods(self) -> None:
        """Test that DisplayProtocol methods work correctly."""
        # Create an instance of DisplayProtocol
        # Note: Protocol classes themselves can't be instantiated
        # but we can test that the protocol is correctly defined
        
        # Test that the protocol has the expected methods
        assert hasattr(DisplayProtocol, 'display')
        assert hasattr(DisplayProtocol, 'display_partial')
        
        # Create a mock that conforms to the protocol
        mock_display = MagicMock(spec=DisplayProtocol)
        image = Image.new("L", (100, 100), 128)
        
        # Test that the mock has the expected methods
        mock_display.display(image)
        mock_display.display.assert_called_once_with(image)
        
        bbox = (10, 20, 90, 80)
        mock_display.display_partial(image, bbox)
        mock_display.display_partial.assert_called_once_with(image, bbox)
        
        # Test with None bbox
        mock_display.display_partial(image, None)
        mock_display.display_partial.assert_called_with(image, None)