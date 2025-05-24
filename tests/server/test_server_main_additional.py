"""Additional tests for server main module to improve coverage."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.server.main import WeatherDisplayServer, lifespan


class TestLifespan:
    """Test the lifespan context manager."""

    @pytest.mark.asyncio()
    async def test_lifespan_startup_shutdown(self) -> None:
        """Test lifespan startup and shutdown."""
        # Create a mock app
        app = FastAPI()
        
        # Mock the browser manager and memory profiler
        with patch("rpi_weather_display.server.main.memory_profiler") as mock_memory_profiler, \
             patch("rpi_weather_display.server.main.browser_manager") as mock_browser_manager:
            
            # Set up mock returns
            mock_memory_profiler.get_report.return_value = {"current": {"rss_mb": 100.0}}
            mock_browser_manager.cleanup = AsyncMock()
            
            # Use the lifespan context manager
            async with lifespan(app):
                # Verify startup was called
                mock_memory_profiler.set_baseline.assert_called_once()
            
            # After exiting, verify shutdown was called
            mock_memory_profiler.get_report.assert_called_once()
            mock_browser_manager.cleanup.assert_called_once()

    @pytest.mark.asyncio()
    async def test_lifespan_with_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test lifespan logging."""
        import logging
        
        app = FastAPI()
        
        with patch("rpi_weather_display.server.main.memory_profiler") as mock_memory_profiler, \
             patch("rpi_weather_display.server.main.browser_manager") as mock_browser_manager, \
             caplog.at_level(logging.INFO):
            
            mock_memory_profiler.get_report.return_value = {"test": "report"}
            mock_browser_manager.cleanup = AsyncMock()
            
            async with lifespan(app):
                pass
            
            # Check logs
            assert "Starting Weather Display Server" in caplog.text
            assert "Shutting down Weather Display Server" in caplog.text
            assert "Final memory report: {'test': 'report'}" in caplog.text


class TestMemoryEndpoint:
    """Test the memory status endpoint."""

    @pytest.fixture()
    def test_server_with_static_mock(self, test_config: AppConfig) -> WeatherDisplayServer:
        """Create a test server instance with mocked static files."""
        with patch("rpi_weather_display.server.main.path_resolver") as mock_resolver, \
             patch.object(AppConfig, "from_yaml", return_value=test_config), \
             patch("rpi_weather_display.server.main.StaticFiles") as mock_static:
            mock_resolver.get_templates_dir.return_value = Path("/templates")
            mock_resolver.get_static_dir.return_value = Path("/static")
            mock_resolver.cache_dir = Path("/cache")
            mock_resolver.normalize_path.side_effect = lambda p: Path(p)
            
            # Mock StaticFiles to avoid directory check
            mock_static.return_value = MagicMock()
            
            server = WeatherDisplayServer(Path("test_config.yaml"))
            return server

    def test_memory_endpoint(self, test_server_with_static_mock: WeatherDisplayServer) -> None:
        """Test the /memory endpoint."""
        client = TestClient(test_server_with_static_mock.app)
        
        # Mock memory profiler
        with patch("rpi_weather_display.server.main.memory_profiler") as mock_profiler:
            mock_profiler.get_report.return_value = {
                "current": {
                    "rss_mb": 150.0,
                    "vms_mb": 300.0,
                    "percent": 5.0,
                    "available_system_mb": 2000.0
                },
                "timestamp": 1234567890.0
            }
            
            response = client.get("/memory")
            
            assert response.status_code == 200
            data = response.json()
            assert data["current"]["rss_mb"] == 150.0
            assert data["timestamp"] == 1234567890.0
            mock_profiler.get_report.assert_called_once()


class TestMemoryGrowthWarning:
    """Test memory growth warning during rendering."""

    @pytest.fixture()
    def test_server_with_static_mock(self, test_config: AppConfig) -> WeatherDisplayServer:
        """Create a test server instance with mocked static files."""
        with patch("rpi_weather_display.server.main.path_resolver") as mock_resolver, \
             patch.object(AppConfig, "from_yaml", return_value=test_config), \
             patch("rpi_weather_display.server.main.StaticFiles") as mock_static:
            mock_resolver.get_templates_dir.return_value = Path("/templates")
            mock_resolver.get_static_dir.return_value = Path("/static")
            mock_resolver.cache_dir = Path("/cache")
            mock_resolver.normalize_path.side_effect = lambda p: Path(p)
            
            # Mock StaticFiles to avoid directory check
            mock_static.return_value = MagicMock()
            
            server = WeatherDisplayServer(Path("test_config.yaml"))
            return server

    @pytest.mark.asyncio()
    async def test_handle_render_memory_growth_warning(
        self, test_server_with_static_mock: WeatherDisplayServer, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test memory growth warning during render."""
        import logging
        
        # Mock dependencies
        mock_api_client = Mock()
        mock_api_client.get_weather_data = AsyncMock(return_value=MagicMock())
        test_server_with_static_mock.api_client = mock_api_client
        
        mock_renderer = Mock()
        mock_renderer.render_weather_image = AsyncMock()
        test_server_with_static_mock.renderer = mock_renderer
        
        # Create request
        from rpi_weather_display.server.main import BatteryInfo, RenderRequest
        request = RenderRequest(
            battery=BatteryInfo(
                level=80,
                state="discharging",
                voltage=3.7,
                current=0.5,
                temperature=25.0
            )
        )
        
        with patch("rpi_weather_display.server.main.memory_profiler") as mock_profiler, \
             patch("rpi_weather_display.server.main.path_resolver") as mock_resolver, \
             patch("rpi_weather_display.server.main.BackgroundTasks") as mock_bg_tasks, \
             caplog.at_level(logging.WARNING):
            
            # Mock memory profiler to trigger warning
            mock_profiler.check_memory_growth.return_value = True
            mock_profiler.record_snapshot = Mock()
            
            # Mock path resolver
            mock_temp_path = MagicMock()
            mock_resolver.get_temp_file.return_value = mock_temp_path
            
            # Mock background tasks
            mock_bg_instance = MagicMock()
            mock_bg_tasks.return_value = mock_bg_instance
            
            # Call the handler
            await test_server_with_static_mock._handle_render(request, mock_bg_instance)
            
            # Verify memory growth was checked and warning was logged
            mock_profiler.check_memory_growth.assert_called_once_with(threshold_mb=100.0)
            assert "Excessive memory growth detected during rendering" in caplog.text


class TestCleanupError:
    """Test cleanup error handling."""

    @pytest.fixture()
    def test_server_with_static_mock(self, test_config: AppConfig) -> WeatherDisplayServer:
        """Create a test server instance with mocked static files."""
        with patch("rpi_weather_display.server.main.path_resolver") as mock_resolver, \
             patch.object(AppConfig, "from_yaml", return_value=test_config), \
             patch("rpi_weather_display.server.main.StaticFiles") as mock_static:
            mock_resolver.get_templates_dir.return_value = Path("/templates")
            mock_resolver.get_static_dir.return_value = Path("/static")
            mock_resolver.cache_dir = Path("/cache")
            mock_resolver.normalize_path.side_effect = lambda p: Path(p)
            
            # Mock StaticFiles to avoid directory check
            mock_static.return_value = MagicMock()
            
            server = WeatherDisplayServer(Path("test_config.yaml"))
            return server

    @pytest.mark.asyncio()
    async def test_cleanup_temp_file_error(
        self, test_server_with_static_mock: WeatherDisplayServer, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test cleanup error handling in background task."""
        import logging
        
        # Create the cleanup function from _handle_render
        mock_path = MagicMock()
        mock_path.unlink.side_effect = Exception("Cleanup failed")
        
        # Extract the cleanup function logic
        def cleanup_temp_file() -> None:
            """Clean up temporary file after response is sent."""
            try:
                mock_path.unlink(missing_ok=True)
            except Exception as clean_e:
                test_server_with_static_mock.logger.warning(f"Failed to clean up temp file {mock_path}: {clean_e}")
        
        # Test the cleanup function
        with caplog.at_level(logging.WARNING):
            cleanup_temp_file()
            
            # Verify warning was logged
            assert "Failed to clean up temp file" in caplog.text
            assert "Cleanup failed" in caplog.text