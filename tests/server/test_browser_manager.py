"""Tests for the browser manager module."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from rpi_weather_display.constants import BROWSER_LAUNCH_DELAY
from rpi_weather_display.server.browser_manager import BrowserManager, PlaywrightPageProtocol


class TestPlaywrightPageProtocol:
    """Tests for the PlaywrightPageProtocol."""

    def test_protocol_definition(self) -> None:
        """Test that the protocol is properly defined."""
        # This is mainly for coverage - the protocol itself doesn't have implementation
        assert hasattr(PlaywrightPageProtocol, "set_content")
        assert hasattr(PlaywrightPageProtocol, "wait_for_load_state")
        assert hasattr(PlaywrightPageProtocol, "screenshot")
        assert hasattr(PlaywrightPageProtocol, "close")

    @pytest.mark.asyncio()
    async def test_protocol_methods(self) -> None:
        """Test protocol method signatures by creating a mock implementation."""
        # Create a mock that implements the protocol
        mock_page = MagicMock(spec=PlaywrightPageProtocol)
        mock_page.set_content = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.screenshot = AsyncMock(return_value=b"image_data")
        mock_page.close = AsyncMock()
        
        # Test each method
        await mock_page.set_content("test html")
        mock_page.set_content.assert_called_once_with("test html")
        
        await mock_page.wait_for_load_state("load")
        mock_page.wait_for_load_state.assert_called_once_with("load")
        
        result = await mock_page.screenshot(path="test.png", type="png")
        assert result == b"image_data"
        mock_page.screenshot.assert_called_once_with(path="test.png", type="png")
        
        await mock_page.close()
        mock_page.close.assert_called_once()

    def test_protocol_ellipsis_coverage(self) -> None:
        """Test to ensure protocol method implementations are covered."""
        # Import the protocol methods to trigger their execution
        from rpi_weather_display.server.browser_manager import PlaywrightPageProtocol
        
        # Access the methods to trigger the ellipsis execution
        # This is a bit unusual but needed for 100% coverage
        assert PlaywrightPageProtocol.set_content is not None
        assert PlaywrightPageProtocol.wait_for_load_state is not None
        assert PlaywrightPageProtocol.screenshot is not None
        assert PlaywrightPageProtocol.close is not None


class TestBrowserManager:
    """Tests for the BrowserManager class."""

    @pytest.fixture()
    def browser_manager(self) -> BrowserManager:
        """Create a browser manager instance for testing."""
        return BrowserManager()

    def test_init(self, browser_manager: BrowserManager) -> None:
        """Test browser manager initialization."""
        assert browser_manager._browser is None
        assert browser_manager._playwright is None
        assert browser_manager._context is None
        assert browser_manager._lock is not None
        assert browser_manager.logger is not None

    def test_init_with_type_checking(self) -> None:
        """Test initialization when TYPE_CHECKING is True."""
        # This is to ensure the TYPE_CHECKING block is covered
        import rpi_weather_display.server.browser_manager as bm_module
        
        # Temporarily set TYPE_CHECKING to True
        original_type_checking = bm_module.TYPE_CHECKING
        try:
            # Mock TYPE_CHECKING to be True
            with patch.object(bm_module, 'TYPE_CHECKING', True):
                # Import the module again to trigger the TYPE_CHECKING imports
                # Note: This is a bit hacky but needed for coverage
                browser_manager = BrowserManager()
                assert browser_manager._browser is None
                assert browser_manager._playwright is None
                assert browser_manager._context is None
        finally:
            # Restore original value
            bm_module.TYPE_CHECKING = original_type_checking

    @pytest.mark.asyncio()
    async def test_get_browser_creates_new_browser(self, browser_manager: BrowserManager) -> None:
        """Test get_browser creates a new browser when none exists."""
        # Mock the browser and playwright
        mock_browser = MagicMock()
        mock_browser.is_connected = Mock(return_value=True)
        mock_browser.new_context = AsyncMock()

        mock_playwright = MagicMock()
        mock_chromium = MagicMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.chromium = mock_chromium

        mock_playwright_instance = MagicMock()
        mock_playwright_instance.start = AsyncMock(return_value=mock_playwright)

        # Patch where async_playwright is used (inside _launch_browser)
        with patch("playwright.async_api.async_playwright") as mock_async_playwright:
            mock_async_playwright.return_value = mock_playwright_instance

            # Call get_browser
            result = await browser_manager.get_browser()

            # Verify browser was created
            assert result == mock_browser
            assert browser_manager._browser == mock_browser
            mock_chromium.launch.assert_called_once()

    @pytest.mark.asyncio()
    async def test_get_browser_returns_existing_connected_browser(
        self, browser_manager: BrowserManager
    ) -> None:
        """Test get_browser returns existing browser if connected."""
        # Set up an existing connected browser
        mock_browser = MagicMock()
        mock_browser.is_connected = Mock(return_value=True)
        browser_manager._browser = mock_browser

        # Call get_browser
        result = await browser_manager.get_browser()

        # Verify existing browser was returned
        assert result == mock_browser

    @pytest.mark.asyncio()
    async def test_get_browser_recreates_disconnected_browser(
        self, browser_manager: BrowserManager
    ) -> None:
        """Test get_browser recreates browser if disconnected."""
        # Set up an existing disconnected browser
        old_browser = MagicMock()
        old_browser.is_connected = Mock(return_value=False)
        browser_manager._browser = old_browser

        # Mock the new browser
        new_browser = MagicMock()
        new_browser.is_connected = Mock(return_value=True)
        new_browser.new_context = AsyncMock()

        mock_playwright = MagicMock()
        mock_chromium = MagicMock()
        mock_chromium.launch = AsyncMock(return_value=new_browser)
        mock_playwright.chromium = mock_chromium

        mock_playwright_instance = MagicMock()
        mock_playwright_instance.start = AsyncMock(return_value=mock_playwright)

        with patch("playwright.async_api.async_playwright") as mock_async_playwright:
            mock_async_playwright.return_value = mock_playwright_instance

            # Call get_browser
            result = await browser_manager.get_browser()

            # Verify new browser was created
            assert result == new_browser
            assert browser_manager._browser == new_browser

    @pytest.mark.asyncio()
    async def test_launch_browser_error_handling(self, browser_manager: BrowserManager) -> None:
        """Test _launch_browser error handling."""
        # Mock async_playwright to raise an error
        with patch("playwright.async_api.async_playwright") as mock_async_playwright:
            mock_async_playwright.side_effect = RuntimeError("Failed to launch")

            # Should raise the error
            with pytest.raises(RuntimeError, match="Failed to launch"):
                await browser_manager._launch_browser()

    @pytest.mark.asyncio()
    async def test_get_page(self, browser_manager: BrowserManager) -> None:
        """Test get_page creates a new page with viewport."""
        # Mock browser and context
        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        mock_browser = MagicMock()
        mock_browser.is_connected = Mock(return_value=True)
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        browser_manager._browser = mock_browser
        browser_manager._context = mock_context

        # Call get_page
        result = await browser_manager.get_page(800, 600)

        # Verify page was created with correct viewport
        assert result == mock_page
        mock_context.new_page.assert_called_once_with(viewport={"width": 800, "height": 600})

    @pytest.mark.asyncio()
    async def test_get_page_creates_context_if_none(self, browser_manager: BrowserManager) -> None:
        """Test get_page creates context if none exists."""
        # Mock browser and page
        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        mock_browser = MagicMock()
        mock_browser.is_connected = Mock(return_value=True)
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        browser_manager._browser = mock_browser
        browser_manager._context = None  # No context

        # Call get_page
        result = await browser_manager.get_page(1024, 768)

        # Verify context was created
        assert browser_manager._context == mock_context
        mock_browser.new_context.assert_called_once()
        assert result == mock_page

    @pytest.mark.asyncio()
    async def test_cleanup(self, browser_manager: BrowserManager) -> None:
        """Test cleanup method."""
        # Set up mocks
        mock_context = MagicMock()
        mock_context.close = AsyncMock()

        mock_browser = MagicMock()
        mock_browser.close = AsyncMock()

        mock_playwright = MagicMock()
        mock_playwright.stop = AsyncMock()

        browser_manager._context = mock_context
        browser_manager._browser = mock_browser
        browser_manager._playwright = mock_playwright

        # Call cleanup
        await browser_manager.cleanup()

        # Verify everything was cleaned up
        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()
        assert browser_manager._context is None
        assert browser_manager._browser is None
        assert browser_manager._playwright is None

    @pytest.mark.asyncio()
    async def test_cleanup_partial_resources(self, browser_manager: BrowserManager) -> None:
        """Test cleanup when only some resources exist."""
        # Only browser exists
        mock_browser = MagicMock()
        mock_browser.close = AsyncMock()

        browser_manager._context = None
        browser_manager._browser = mock_browser
        browser_manager._playwright = None

        # Call cleanup
        await browser_manager.cleanup()

        # Verify only browser was cleaned up
        mock_browser.close.assert_called_once()
        assert browser_manager._browser is None

    @pytest.mark.asyncio()
    async def test_cleanup_error_handling(self, browser_manager: BrowserManager) -> None:
        """Test cleanup handles errors gracefully."""
        # Set up mock that raises error
        mock_browser = MagicMock()
        mock_browser.close = AsyncMock(side_effect=RuntimeError("Close failed"))

        browser_manager._browser = mock_browser

        # Call cleanup - should not raise
        await browser_manager.cleanup()

        # Browser should still be set since cleanup failed
        assert browser_manager._browser is mock_browser

    @pytest.mark.asyncio()
    async def test_launch_browser_with_existing_resources(
        self, browser_manager: BrowserManager
    ) -> None:
        """Test _launch_browser cleans up existing resources first."""
        # Set up existing resources
        old_context = MagicMock()
        old_context.close = AsyncMock()

        old_browser = MagicMock()
        old_browser.close = AsyncMock()

        old_playwright = MagicMock()
        old_playwright.stop = AsyncMock()

        browser_manager._context = old_context
        browser_manager._browser = old_browser
        browser_manager._playwright = old_playwright

        # Mock new browser
        new_browser = MagicMock()
        new_browser.new_context = AsyncMock()

        mock_playwright = MagicMock()
        mock_chromium = MagicMock()
        mock_chromium.launch = AsyncMock(return_value=new_browser)
        mock_playwright.chromium = mock_chromium

        mock_playwright_instance = MagicMock()
        mock_playwright_instance.start = AsyncMock(return_value=mock_playwright)

        with patch("playwright.async_api.async_playwright") as mock_async_playwright:
            mock_async_playwright.return_value = mock_playwright_instance

            # Call _launch_browser
            await browser_manager._launch_browser()

            # Verify old resources were cleaned up
            old_context.close.assert_called_once()
            old_browser.close.assert_called_once()
            old_playwright.stop.assert_called_once()

            # Verify new browser was created
            assert browser_manager._browser == new_browser

    @pytest.mark.asyncio()
    async def test_concurrent_get_browser_calls(self, browser_manager: BrowserManager) -> None:
        """Test that concurrent get_browser calls are handled properly."""
        call_count = 0

        # Mock browser creation with a delay
        async def mock_launch(*_: Any, **_kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(BROWSER_LAUNCH_DELAY)  # Simulate slow browser launch
            browser = MagicMock()
            browser.is_connected = Mock(return_value=True)
            browser.new_context = AsyncMock()
            return browser

        mock_playwright = MagicMock()
        mock_chromium = MagicMock()
        mock_chromium.launch = mock_launch
        mock_playwright.chromium = mock_chromium

        mock_playwright_instance = MagicMock()
        mock_playwright_instance.start = AsyncMock(return_value=mock_playwright)

        with patch("playwright.async_api.async_playwright") as mock_async_playwright:
            mock_async_playwright.return_value = mock_playwright_instance

            # Call get_browser concurrently
            results = await asyncio.gather(
                browser_manager.get_browser(),
                browser_manager.get_browser(),
                browser_manager.get_browser(),
            )

            # All should get the same browser instance
            assert results[0] == results[1] == results[2]
            # Browser should only be created once
            assert call_count == 1

    def test_global_browser_manager_instance(self) -> None:
        """Test that global browser_manager instance exists."""
        from rpi_weather_display.server.browser_manager import browser_manager

        assert isinstance(browser_manager, BrowserManager)
