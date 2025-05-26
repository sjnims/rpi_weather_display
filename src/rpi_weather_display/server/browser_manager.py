"""Browser management for efficient Playwright usage.

Provides a singleton browser instance to avoid the overhead of launching
a new browser for each render operation, significantly reducing memory usage.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Protocol

from rpi_weather_display.utils.error_utils import get_error_location

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Playwright


class PlaywrightPageProtocol(Protocol):
    """Protocol for Playwright Page interface."""

    async def set_content(self, html: str) -> None:
        """Set page content."""
        ...

    async def wait_for_load_state(self, state: str) -> None:
        """Wait for load state."""
        ...

    async def screenshot(self, path: str | None = None, type: str = "png") -> bytes:  # noqa: A002
        """Take screenshot."""
        ...

    async def close(self) -> None:
        """Close the page."""
        ...


class BrowserManager:
    """Manages a singleton Playwright browser instance for efficient rendering."""

    def __init__(self) -> None:
        """Initialize the browser manager."""
        self.logger = logging.getLogger(__name__)
        if TYPE_CHECKING:
            self._browser: Browser | None = None
            self._playwright: Playwright | None = None
            self._context: BrowserContext | None = None
        else:
            self._browser = None
            self._playwright = None
            self._context = None
        self._lock = asyncio.Lock()

    async def get_browser(self) -> object:
        """Get or create the browser instance.

        Returns:
            The browser instance.
        """
        async with self._lock:
            if self._browser is None or not self._browser.is_connected():
                await self._launch_browser()
            return self._browser

    async def _launch_browser(self) -> None:
        """Launch a new browser instance."""
        try:
            # Close existing if any
            await self._cleanup()

            # Dynamic import to avoid import errors when playwright isn't installed
            from playwright.async_api import async_playwright

            # Launch new browser
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-zygote",
                    "--single-process",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            self._context = await self._browser.new_context()
            self.logger.info("Browser launched successfully")
        except Exception as e:
            error_location = get_error_location()
            self.logger.error(f"Failed to launch browser [{error_location}]: {e}")
            raise

    async def get_page(self, width: int, height: int) -> PlaywrightPageProtocol:
        """Get a new page with specified viewport.

        Args:
            width: Viewport width
            height: Viewport height

        Returns:
            A new page instance.
        """
        browser = await self.get_browser()
        if self._context is None:
            self._context = await browser.new_context()  # type: ignore

        return await self._context.new_page(viewport={"width": width, "height": height})  # type: ignore

    async def cleanup(self) -> None:
        """Clean up browser resources."""
        async with self._lock:
            await self._cleanup()

    async def _cleanup(self) -> None:
        """Internal cleanup method."""
        try:
            if self._context:
                await self._context.close()
                self._context = None
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            self.logger.info("Browser cleaned up")
        except Exception as e:
            self.logger.error(f"Error during browser cleanup: {e}")


# Global browser manager instance
browser_manager = BrowserManager()
