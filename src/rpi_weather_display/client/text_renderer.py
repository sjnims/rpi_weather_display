"""Text rendering utilities for e-paper display.

Handles text image generation with appropriate fonts and positioning
for displaying messages and alerts on the e-paper display.
"""

# pyright: reportUnknownMemberType=false

from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

from rpi_weather_display.constants import (
    DEFAULT_MESSAGE_FONT,
    DEFAULT_TITLE_FONT,
    FONT_SIZE_DIVIDER,
    FONT_SIZE_MESSAGE_DIVIDER,
    MESSAGE_FONT_SIZE_BASE,
    MESSAGE_FONT_SIZE_MAX,
    MESSAGE_Y_POSITION_FACTOR,
    TITLE_FONT_SIZE_BASE,
    TITLE_FONT_SIZE_MAX,
    TITLE_Y_POSITION_FACTOR,
)
from rpi_weather_display.exceptions import ImageRenderingError, chain_exception

if TYPE_CHECKING:
    from rpi_weather_display.models.config import DisplayConfig


class TextRenderer:
    """Renders text content for e-paper display.
    
    This class handles the creation of text-based images for displaying
    messages, alerts, and status information on the e-paper display.
    
    Attributes:
        config: Display configuration with dimensions
    """
    
    def __init__(self, config: "DisplayConfig") -> None:
        """Initialize the text renderer.
        
        Args:
            config: Display configuration containing dimensions
        """
        self.config = config
        
    def render_text_image(self, title: str, message: str) -> Image.Image:
        """Create an image with rendered text.
        
        Generates a white background image with black text positioned
        appropriately for the display size.
        
        Args:
            title: Title text to display at the top
            message: Main message text to display below title
            
        Returns:
            PIL Image with rendered text
            
        Raises:
            ImageRenderingError: If text rendering fails
        """
        try:
            # Create blank white image
            image = Image.new("L", (self.config.width, self.config.height), 255)
            draw = ImageDraw.Draw(image)
            
            # Load fonts
            title_font = self._load_title_font()
            message_font = self._load_message_font()
            
            # Render title
            self._render_title(draw, title, title_font)
            
            # Render message
            self._render_message(draw, message, message_font)
            
            return image
            
        except Exception as e:
            raise chain_exception(
                ImageRenderingError(
                    "Failed to render text image",
                    {
                        "title": title,
                        "message": message,
                        "display_size": (self.config.width, self.config.height),
                        "error": str(e)
                    }
                ),
                e
            ) from None
        
    def _load_title_font(self) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Load font for title text.
        
        Returns:
            Font object for title rendering
            
        Raises:
            ImageRenderingError: If font loading fails completely
        """
        title_font_size = self._calculate_title_font_size()
        
        try:
            return ImageFont.truetype(DEFAULT_TITLE_FONT, title_font_size)
        except OSError as e:
            # Try to fall back to default font
            try:
                return ImageFont.load_default()
            except Exception as fallback_error:
                raise chain_exception(
                    ImageRenderingError(
                        "Failed to load title font",
                        {
                            "font_path": DEFAULT_TITLE_FONT,
                            "font_size": title_font_size,
                            "original_error": str(e),
                            "fallback_error": str(fallback_error)
                        }
                    ),
                    fallback_error
                ) from None
            
    def _load_message_font(self) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Load font for message text.
        
        Returns:
            Font object for message rendering
            
        Raises:
            ImageRenderingError: If font loading fails completely
        """
        message_font_size = self._calculate_message_font_size()
        
        try:
            return ImageFont.truetype(DEFAULT_MESSAGE_FONT, message_font_size)
        except OSError as e:
            # Try to fall back to default font
            try:
                return ImageFont.load_default()
            except Exception as fallback_error:
                raise chain_exception(
                    ImageRenderingError(
                        "Failed to load message font",
                        {
                            "font_path": DEFAULT_MESSAGE_FONT,
                            "font_size": message_font_size,
                            "original_error": str(e),
                            "fallback_error": str(fallback_error)
                        }
                    ),
                    fallback_error
                ) from None
            
    def _calculate_title_font_size(self) -> int:
        """Calculate appropriate title font size.
        
        Returns:
            Font size for title text
        """
        return max(
            TITLE_FONT_SIZE_BASE,
            min(TITLE_FONT_SIZE_MAX, self.config.width // FONT_SIZE_DIVIDER)
        )
        
    def _calculate_message_font_size(self) -> int:
        """Calculate appropriate message font size.
        
        Returns:
            Font size for message text
        """
        return max(
            MESSAGE_FONT_SIZE_BASE,
            min(MESSAGE_FONT_SIZE_MAX, self.config.width // FONT_SIZE_MESSAGE_DIVIDER)
        )
        
    def _render_title(
        self,
        draw: ImageDraw.ImageDraw,
        title: str,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont
    ) -> None:
        """Render title text on the image.
        
        Args:
            draw: ImageDraw object
            title: Title text to render
            font: Font to use for rendering
        """
        # Calculate position
        title_bbox = draw.textbbox((0, 0), title, font=font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (self.config.width - title_width) // 2
        title_y = self.config.height // TITLE_Y_POSITION_FACTOR
        
        # Draw text
        draw.text((title_x, title_y), title, font=font, fill=0)
        
    def _render_message(
        self,
        draw: ImageDraw.ImageDraw,
        message: str,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont
    ) -> None:
        """Render message text on the image.
        
        Args:
            draw: ImageDraw object
            message: Message text to render
            font: Font to use for rendering
        """
        # Calculate position
        message_bbox = draw.textbbox((0, 0), message, font=font)
        message_width = message_bbox[2] - message_bbox[0]
        message_x = (self.config.width - message_width) // 2
        message_y = self.config.height // MESSAGE_Y_POSITION_FACTOR
        
        # Draw text
        draw.text((message_x, message_y), message, font=font, fill=0)