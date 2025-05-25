"""Tests for text renderer."""

from unittest.mock import MagicMock, patch

from PIL import Image, ImageDraw

from rpi_weather_display.client.text_renderer import TextRenderer
from rpi_weather_display.models.config import DisplayConfig


class TestTextRenderer:
    """Test cases for TextRenderer."""

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
        )
        self.renderer = TextRenderer(self.config)

    def test_init(self) -> None:
        """Test initialization."""
        assert self.renderer.config == self.config

    def test_render_text_image(self) -> None:
        """Test render_text_image creates image with text."""
        title = "Test Title"
        message = "Test Message"
        
        result = self.renderer.render_text_image(title, message)
        
        assert isinstance(result, Image.Image)
        assert result.size == (self.config.width, self.config.height)
        assert result.mode == "L"


    def test_calculate_title_font_size(self) -> None:
        """Test title font size calculation."""
        # Default config should calculate based on width
        font_size = self.renderer._calculate_title_font_size()
        
        # Should be within expected range
        assert font_size >= 36  # TITLE_FONT_SIZE_BASE
        assert font_size <= 48  # TITLE_FONT_SIZE_MAX
        
        # For width 1872, should be min(48, 1872 // 20) = min(48, 93.6) = 48
        expected = min(48, 1872 // 20)
        assert font_size == expected

    def test_calculate_title_font_size_small_display(self) -> None:
        """Test title font size for small display."""
        # Create renderer with small display
        small_config = DisplayConfig(
            width=400,
            height=300,
            rotate=0,
            vcom=-2.06,
            refresh_interval_minutes=30,
            partial_refresh=True,
            timestamp_format="%Y-%m-%d %H:%M",
        )
        renderer = TextRenderer(small_config)
        
        font_size = renderer._calculate_title_font_size()
        
        # Should be at minimum
        assert font_size == 36  # TITLE_FONT_SIZE_BASE

    def test_calculate_title_font_size_large_display(self) -> None:
        """Test title font size for large display."""
        # Create renderer with large display
        large_config = DisplayConfig(
            width=3000,
            height=2000,
            rotate=0,
            vcom=-2.06,
            refresh_interval_minutes=30,
            partial_refresh=True,
            timestamp_format="%Y-%m-%d %H:%M",
        )
        renderer = TextRenderer(large_config)
        
        font_size = renderer._calculate_title_font_size()
        
        # Should be at maximum
        assert font_size == 48  # TITLE_FONT_SIZE_MAX

    def test_calculate_message_font_size(self) -> None:
        """Test message font size calculation."""
        font_size = self.renderer._calculate_message_font_size()
        
        # Should be within expected range
        assert font_size >= 24  # MESSAGE_FONT_SIZE_BASE
        assert font_size <= 36  # MESSAGE_FONT_SIZE_MAX
        
        # For width 1872, should be min(36, 1872 // 30) = min(36, 62.4) = 36
        expected = min(36, 1872 // 30)
        assert font_size == expected

    def test_calculate_message_font_size_small_display(self) -> None:
        """Test message font size for small display."""
        # Create renderer with small display
        small_config = DisplayConfig(
            width=400,
            height=300,
            rotate=0,
            vcom=-2.06,
            refresh_interval_minutes=30,
            partial_refresh=True,
            timestamp_format="%Y-%m-%d %H:%M",
        )
        renderer = TextRenderer(small_config)
        
        font_size = renderer._calculate_message_font_size()
        
        # Should be at minimum
        assert font_size == 24  # MESSAGE_FONT_SIZE_BASE

    @patch("PIL.ImageFont.truetype")
    def test_load_title_font_success(self, mock_truetype: MagicMock) -> None:
        """Test successful title font loading."""
        mock_font = MagicMock()
        mock_truetype.return_value = mock_font
        
        result = self.renderer._load_title_font()
        
        assert result == mock_font
        mock_truetype.assert_called_once()

    @patch("PIL.ImageFont.truetype")
    @patch("PIL.ImageFont.load_default")
    def test_load_title_font_fallback(
        self, mock_load_default: MagicMock, mock_truetype: MagicMock
    ) -> None:
        """Test title font fallback to default."""
        mock_truetype.side_effect = OSError("Font not found")
        mock_default_font = MagicMock()
        mock_load_default.return_value = mock_default_font
        
        result = self.renderer._load_title_font()
        
        assert result == mock_default_font
        mock_load_default.assert_called_once()

    @patch("PIL.ImageFont.truetype")
    def test_load_message_font_success(self, mock_truetype: MagicMock) -> None:
        """Test successful message font loading."""
        mock_font = MagicMock()
        mock_truetype.return_value = mock_font
        
        result = self.renderer._load_message_font()
        
        assert result == mock_font
        mock_truetype.assert_called_once()

    @patch("PIL.ImageFont.truetype")
    @patch("PIL.ImageFont.load_default")
    def test_load_message_font_fallback(
        self, mock_load_default: MagicMock, mock_truetype: MagicMock
    ) -> None:
        """Test message font fallback to default."""
        mock_truetype.side_effect = OSError("Font not found")
        mock_default_font = MagicMock()
        mock_load_default.return_value = mock_default_font
        
        result = self.renderer._load_message_font()
        
        assert result == mock_default_font
        mock_load_default.assert_called_once()

    def test_render_title(self) -> None:
        """Test _render_title method."""
        # Create mock draw object
        mock_draw = MagicMock(spec=ImageDraw.ImageDraw)
        mock_draw.textbbox.return_value = (0, 0, 200, 50)  # Mock text dimensions
        
        # Create mock font
        mock_font = MagicMock()
        
        title = "Test Title"
        self.renderer._render_title(mock_draw, title, mock_font)
        
        # Verify text was drawn
        mock_draw.text.assert_called_once()
        call_args = mock_draw.text.call_args
        
        # Check position (should be centered)
        position = call_args[0][0]
        expected_x = (self.config.width - 200) // 2
        expected_y = self.config.height // 3  # TITLE_Y_POSITION_FACTOR = 3
        assert position == (expected_x, expected_y)
        
        # Check text and other arguments
        assert call_args[0][1] == title
        assert call_args[1]["font"] == mock_font
        assert call_args[1]["fill"] == 0  # Black text

    def test_render_message(self) -> None:
        """Test _render_message method."""
        # Create mock draw object
        mock_draw = MagicMock(spec=ImageDraw.ImageDraw)
        mock_draw.textbbox.return_value = (0, 0, 300, 40)  # Mock text dimensions
        
        # Create mock font
        mock_font = MagicMock()
        
        message = "Test Message"
        self.renderer._render_message(mock_draw, message, mock_font)
        
        # Verify text was drawn
        mock_draw.text.assert_called_once()
        call_args = mock_draw.text.call_args
        
        # Check position (should be centered)
        position = call_args[0][0]
        expected_x = (self.config.width - 300) // 2
        expected_y = self.config.height // 2  # MESSAGE_Y_POSITION_FACTOR = 2
        assert position == (expected_x, expected_y)
        
        # Check text and other arguments
        assert call_args[0][1] == message
        assert call_args[1]["font"] == mock_font
        assert call_args[1]["fill"] == 0  # Black text

    def test_render_text_image_integration(self) -> None:
        """Test full integration of text rendering."""
        title = "System Alert"
        message = "Display initialized successfully"
        
        # Render the image
        image = self.renderer.render_text_image(title, message)
        
        # Verify basic properties
        assert isinstance(image, Image.Image)
        assert image.size == (self.config.width, self.config.height)
        assert image.mode == "L"
        
        # The image should be mostly white (255) since it's a white background
        # We can't easily test the exact text rendering without OCR,
        # but we can verify it's not completely white (text was drawn)
        pixels = list(image.getdata())  # type: ignore[arg-type]
        unique_pixels = set(pixels)
        
        # Should have at least white (255) and black (0) pixels
        assert 255 in unique_pixels  # White background
        assert len(unique_pixels) > 1  # Not just white (text was drawn)