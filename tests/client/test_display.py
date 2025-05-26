"""Tests for the refactored e-paper display module."""

from pathlib import Path
from unittest.mock import MagicMock, create_autospec, patch

import pytest
from PIL import Image

from rpi_weather_display.client.battery_threshold_manager import BatteryThresholdManager
from rpi_weather_display.client.display import (
    EPaperDisplay,
    EPDDisplayProtocol,
    EPDProtocol,
    _import_it8951,
)
from rpi_weather_display.client.image_processor import ImageProcessor
from rpi_weather_display.client.partial_refresh_manager import PartialRefreshManager
from rpi_weather_display.client.text_renderer import TextRenderer
from rpi_weather_display.exceptions import DisplayInitializationError, DisplayUpdateError
from rpi_weather_display.models.config import DisplayConfig
from rpi_weather_display.models.system import BatteryState, BatteryStatus


class MockAutoEPDDisplay:
    """Mock IT8951 AutoEPDDisplay class."""

    def __init__(self, vcom: float) -> None:
        """Initialize mock display."""
        self.vcom = vcom
        self.width = 1872
        self.height = 1404
        self.epd = MagicMock(spec=EPDProtocol)

    def display(self, img: Image.Image) -> None:
        """Mock display method."""
        pass

    def display_partial(
        self, img: Image.Image, bbox: tuple[int, int, int, int] | None = None
    ) -> None:
        """Mock partial display method."""
        pass

    def clear(self) -> None:
        """Mock clear method."""
        pass

    def sleep(self) -> None:
        """Mock sleep method."""
        self.epd.sleep()


class TestDisplayHelpers:
    """Test helper functions."""

    def test_import_it8951_success(self) -> None:
        """Test successful IT8951 import."""
        with patch("builtins.__import__") as mock_import:
            # Create a mock module with AutoEPDDisplay
            mock_module = MagicMock()
            mock_module.display.AutoEPDDisplay = MockAutoEPDDisplay
            mock_import.return_value = mock_module
            
            result = _import_it8951()
            assert result is not None

    def test_import_it8951_failure(self) -> None:
        """Test IT8951 import failure."""
        with patch("builtins.__import__", side_effect=ImportError("Module not found")):
            result = _import_it8951()
            assert result is None


class TestEPaperDisplay:
    """Test cases for EPaperDisplay class."""

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
        self.display = EPaperDisplay(self.config)

    def test_init(self) -> None:
        """Test initialization."""
        assert self.display.config == self.config
        assert self.display._display is None
        assert not self.display._initialized
        
        # Check that component managers are initialized
        assert isinstance(self.display.battery_threshold_manager, BatteryThresholdManager)
        assert isinstance(self.display.image_processor, ImageProcessor)
        assert isinstance(self.display.partial_refresh_manager, PartialRefreshManager)
        assert isinstance(self.display.text_renderer, TextRenderer)

    def test_initialize_success(self) -> None:
        """Test successful display initialization."""
        with patch(
            "rpi_weather_display.client.display._import_it8951",
            return_value=MockAutoEPDDisplay
        ):
            self.display.initialize()
            
            assert self.display._initialized
            assert self.display._display is not None
            assert isinstance(self.display._display, MockAutoEPDDisplay)

    def test_initialize_no_library(self) -> None:
        """Test initialization when IT8951 library is not available."""
        with (
            patch(
                "rpi_weather_display.client.display._import_it8951",
                return_value=None
            ),
            patch.object(self.display.logger, "warning") as mock_warning
        ):
            self.display.initialize()
            
            assert not self.display._initialized
            assert self.display._display is None
            mock_warning.assert_called_with(
                "IT8951 library not available. Using mock display."
            )

    def test_initialize_exception(self) -> None:
        """Test initialization with exception."""
        with patch(
            "rpi_weather_display.client.display._import_it8951",
            side_effect=Exception("Test error")
        ):
            with pytest.raises(DisplayInitializationError) as exc_info:
                self.display.initialize()
                
            assert not self.display._initialized
            assert self.display._display is None
            assert "Failed to initialize e-paper display" in str(exc_info.value)
            assert exc_info.value.details["error"] == "Test error"

    def test_set_rotation(self) -> None:
        """Test display rotation setting."""
        # Set up display with rotation
        self.config.rotate = 90
        display = EPaperDisplay(self.config)
        
        # Create mock display
        mock_display = create_autospec(EPDDisplayProtocol, instance=True)
        mock_epd = create_autospec(EPDProtocol, instance=True)
        mock_display.epd = mock_epd
        
        display._display = mock_display
        display._set_rotation()
        
        # Verify rotation was set (90 degrees = 1 * 90)
        mock_epd.set_rotation.assert_called_once_with(1)

    def test_clear(self) -> None:
        """Test clear method."""
        # Set up initialized display
        mock_display = create_autospec(EPDDisplayProtocol, instance=True)
        self.display._display = mock_display
        self.display._initialized = True
        
        # Mock partial refresh manager
        with patch.object(
            self.display.partial_refresh_manager, 
            "clear_last_image"
        ) as mock_clear_last:
            self.display.clear()
            
            mock_display.clear.assert_called_once()
            mock_clear_last.assert_called_once()

    def test_clear_not_initialized(self) -> None:
        """Test clear when display is not initialized."""
        # Mock partial refresh manager
        with patch.object(
            self.display.partial_refresh_manager, 
            "clear_last_image"
        ) as mock_clear_last:
            self.display.clear()
            
            # Should still clear last image
            mock_clear_last.assert_called_once()

    def test_display_image(self) -> None:
        """Test display_image method."""
        # Create test image file
        test_path = Path("test_image.png")
        test_image_data = b"fake image data"
        
        with (
            patch("rpi_weather_display.client.display.read_bytes", return_value=test_image_data),
            patch("PIL.Image.open") as mock_open,
            patch.object(self.display, "display_pil_image") as mock_display_pil
        ):
            # Create mock image
            mock_image = MagicMock(spec=Image.Image)
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_image)
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_context
            
            self.display.display_image(test_path)
            
            mock_display_pil.assert_called_once_with(mock_image)

    def test_display_pil_image_not_initialized(self) -> None:
        """Test display_pil_image in mock mode."""
        image = Image.new("L", (100, 100), 128)
        
        with (
            patch.object(self.display, "_handle_mock_display") as mock_handle,
            patch.object(self.display.image_processor, "preprocess_image", return_value=image),
            patch.object(self.display.partial_refresh_manager, "update_display")
        ):
            self.display.display_pil_image(image)
            
            mock_handle.assert_called_once_with(image)

    def test_display_pil_image_initialized(self) -> None:
        """Test display_pil_image with initialized display."""
        # Set up initialized display
        mock_display = create_autospec(EPDDisplayProtocol, instance=True)
        self.display._display = mock_display
        self.display._initialized = True
        
        # Create test image
        image = Image.new("L", (100, 100), 128)
        processed_image = Image.new("L", (self.config.width, self.config.height), 128)
        
        with (
            patch.object(
                self.display.image_processor, 
                "preprocess_image", 
                return_value=processed_image
            ),
            patch.object(
                self.display.partial_refresh_manager,
                "update_display",
                return_value=True
            ) as mock_update
        ):
            self.display.display_pil_image(image)
            
            mock_update.assert_called_once_with(processed_image, mock_display)

    def test_display_pil_image_exception(self) -> None:
        """Test display_pil_image with exception."""
        self.display._initialized = True
        self.display._display = MagicMock()
        image = Image.new("L", (100, 100), 128)
        
        with patch.object(
            self.display.image_processor,
            "preprocess_image",
            side_effect=Exception("Test error")
        ):
            with pytest.raises(DisplayUpdateError) as exc_info:
                self.display.display_pil_image(image)
            
            assert "Failed to display image" in str(exc_info.value)
            assert exc_info.value.details["error"] == "Test error"

    def test_handle_mock_display(self) -> None:
        """Test _handle_mock_display method."""
        image = Image.new("L", (100, 100), 128)
        processed_image = Image.new("L", (self.config.width, self.config.height), 128)
        
        with (
            patch.object(self.display.logger, "info") as mock_info,
            patch.object(
                self.display.image_processor,
                "preprocess_image",
                return_value=processed_image
            ),
            patch.object(
                self.display.partial_refresh_manager,
                "update_display"
            ) as mock_update
        ):
            self.display._handle_mock_display(image)
            
            mock_info.assert_called_with("Mock display: would display image of size (100, 100)")
            mock_update.assert_called_once_with(processed_image, None)

    def test_display_text(self) -> None:
        """Test display_text method."""
        title = "Test Title"
        message = "Test Message"
        mock_image = Image.new("L", (self.config.width, self.config.height), 255)
        
        with (
            patch.object(
                self.display.text_renderer,
                "render_text_image",
                return_value=mock_image
            ) as mock_render,
            patch.object(self.display, "display_pil_image") as mock_display
        ):
            self.display.display_text(title, message)
            
            mock_render.assert_called_once_with(title, message)
            mock_display.assert_called_once_with(mock_image)

    def test_display_text_exception(self) -> None:
        """Test display_text with exception."""
        title = "Test Title"
        message = "Test Message"
        
        with patch.object(
            self.display.text_renderer,
            "render_text_image",
            side_effect=Exception("Render error")
        ):
            with pytest.raises(DisplayUpdateError) as exc_info:
                self.display.display_text(title, message)
            
            assert "Failed to display text" in str(exc_info.value)
            assert exc_info.value.details["title"] == title
            assert exc_info.value.details["message"] == message
            assert exc_info.value.details["error"] == "Render error"

    def test_update_battery_status(self) -> None:
        """Test update_battery_status method."""
        battery_status = BatteryStatus(
            level=75,
            voltage=3.8,
            current=-500.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
        )
        
        with patch.object(
            self.display.battery_threshold_manager,
            "update_battery_status"
        ) as mock_update:
            self.display.update_battery_status(battery_status)
            
            mock_update.assert_called_once_with(battery_status)

    def test_sleep(self) -> None:
        """Test sleep method."""
        # Set up initialized display with epd
        mock_display = create_autospec(EPDDisplayProtocol, instance=True)
        mock_epd = create_autospec(EPDProtocol, instance=True)
        mock_display.epd = mock_epd
        
        self.display._display = mock_display
        self.display._initialized = True
        
        self.display.sleep()
        
        mock_epd.sleep.assert_called_once()

    def test_sleep_not_initialized(self) -> None:
        """Test sleep when display is not initialized."""
        # Should not raise any exception
        self.display.sleep()

    def test_sleep_no_epd_attribute(self) -> None:
        """Test sleep when display has no epd attribute."""
        # Set up display without epd
        mock_display = MagicMock(spec=["display", "clear"])
        self.display._display = mock_display
        self.display._initialized = True
        
        # Should not raise AttributeError
        self.display.sleep()

    def test_close(self) -> None:
        """Test close method."""
        # Set up initialized display
        mock_display = create_autospec(EPDDisplayProtocol, instance=True)
        self.display._display = mock_display
        self.display._initialized = True
        
        with (
            patch.object(self.display, "sleep") as mock_sleep,
            patch.object(
                self.display.partial_refresh_manager,
                "clear_last_image"
            ) as mock_clear
        ):
            self.display.close()
            
            mock_sleep.assert_called_once()
            mock_clear.assert_called_once()
            assert not self.display._initialized
            assert self.display._display is None