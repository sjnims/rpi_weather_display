"""Consolidated tests for the weather display server main module.

This file consolidates all server main tests into well-organized test classes.
"""

import json
import logging
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import BackgroundTasks, FastAPI, HTTPException, Response
from fastapi.testclient import TestClient

from rpi_weather_display.constants import (
    CLIENT_CACHE_DIR_NAME,
    DEFAULT_SERVER_HOST,
    SERVER_MEMORY_GROWTH_THRESHOLD_MB,
)
from rpi_weather_display.exceptions import ConfigFileNotFoundError
from rpi_weather_display.models.config import AppConfig, LoggingConfig
from rpi_weather_display.models.system import BatteryState
from rpi_weather_display.models.weather import WeatherData
from rpi_weather_display.server.main import (
    BatteryInfo,
    RenderRequest,
    WeatherDisplayServer,
    lifespan,
    main,
)
from rpi_weather_display.utils.file_utils import create_temp_file
from rpi_weather_display.utils.path_utils import path_resolver, validate_config_path

# Shared mock logger for all tests
_mock_logger = MagicMock()
_mock_logger.info = MagicMock()
_mock_logger.warning = MagicMock()
_mock_logger.error = MagicMock()
_mock_logger.debug = MagicMock()
_mock_logger.handlers = []
_mock_logger.addHandler = MagicMock()
_mock_logger.setLevel = MagicMock()


@pytest.fixture()
def test_server(test_config_path: str) -> WeatherDisplayServer:
    """Create a test server instance."""
    with patch("pathlib.Path.exists", return_value=True):
        config_path = path_resolver.normalize_path(test_config_path)
        return WeatherDisplayServer(config_path)


@pytest.fixture()
def test_server_with_mocks(test_config: AppConfig):
    """Create a test server instance with fully mocked dependencies."""
    mock_app = MagicMock()

    def app_factory() -> FastAPI:
        return mock_app

    with tempfile.TemporaryDirectory() as temp_dir:
        templates_dir = Path(temp_dir) / "templates"
        static_dir = Path(temp_dir) / "static"
        templates_dir.mkdir()
        static_dir.mkdir()

        with (
            patch.object(AppConfig, "from_yaml", return_value=test_config),
            patch("rpi_weather_display.utils.logging.setup_logging", return_value=_mock_logger),
            patch(
                "rpi_weather_display.utils.path_resolver.get_templates_dir",
                return_value=templates_dir,
            ),
            patch(
                "rpi_weather_display.utils.path_resolver.get_static_dir",
                return_value=static_dir,
            ),
            patch("rpi_weather_display.server.main.path_resolver.ensure_dir_exists"),
            patch("fastapi.staticfiles.StaticFiles", return_value=MagicMock()),
        ):
            server = WeatherDisplayServer(Path("test_config.yaml"), app_factory=app_factory)
            yield server


class TestServerInitialization:
    """Tests for server initialization and setup."""

    def test_server_initialization(self, test_server: WeatherDisplayServer) -> None:
        """Test basic server initialization."""
        assert test_server.app is not None
        assert test_server.config is not None
        assert test_server.api_client is not None
        assert test_server.renderer is not None
        assert test_server.cache_dir is not None
        assert test_server.cache_dir.exists()

    def test_cache_dir_fallback(self) -> None:
        """Test cache_dir fallback when not configured."""
        mock_config = MagicMock()
        mock_config.logging = LoggingConfig(level="INFO")
        mock_config.server.cache_dir = None

        mock_cache_dir = Path("/mock/cache/dir")
        mock_app = MagicMock()

        def app_factory() -> FastAPI:
            return mock_app

        with tempfile.TemporaryDirectory() as temp_dir:
            templates_dir = Path(temp_dir) / "templates"
            static_dir = Path(temp_dir) / "static"
            templates_dir.mkdir()
            static_dir.mkdir()
            
            with (
                patch(
                    "rpi_weather_display.models.config.AppConfig.from_yaml",
                    return_value=mock_config,
                ),
                patch("rpi_weather_display.utils.logging.setup_logging", return_value=_mock_logger),
                patch(
                    "rpi_weather_display.utils.path_resolver.get_templates_dir",
                    return_value=templates_dir,
                ),
                patch(
                    "rpi_weather_display.utils.path_resolver.get_static_dir",
                    return_value=static_dir,
                ),
                patch("rpi_weather_display.server.main.path_resolver.cache_dir", mock_cache_dir),
                patch("rpi_weather_display.server.main.path_resolver.ensure_dir_exists"),
                patch("rpi_weather_display.server.main.FileCache", return_value=MagicMock()),
                patch("fastapi.staticfiles.StaticFiles", return_value=MagicMock()),
            ):
                server = WeatherDisplayServer(Path("test_config.yaml"), app_factory=app_factory)
                assert server.cache_dir == mock_cache_dir

    def test_template_dir_fallback(self) -> None:
        """Test fallback template directory path."""
        mock_config = MagicMock()
        mock_config.logging = LoggingConfig(level="INFO")

        mock_templates_dir = Path(f"/etc/{CLIENT_CACHE_DIR_NAME}/templates")

        def get_templates_dir_mock() -> Path:
            return mock_templates_dir

        with (
            patch(
                "rpi_weather_display.models.config.AppConfig.from_yaml", return_value=mock_config
            ),
            patch("rpi_weather_display.utils.logging.setup_logging", return_value=MagicMock()),
            patch(
                "rpi_weather_display.utils.path_utils.PathResolver.get_templates_dir",
                side_effect=get_templates_dir_mock,
            ),
        ):
            server = WeatherDisplayServer(Path("test_config.yaml"))
            assert "templates" in str(server.template_dir)

    def test_static_files_not_found(self) -> None:
        """Test warning when static files directory not found."""
        mock_config = MagicMock()
        mock_config.logging = LoggingConfig(level="INFO")

        mock_logger = MagicMock()
        mock_app = MagicMock()

        def app_factory() -> FastAPI:
            return mock_app

        def patched_exists(path_obj: Path) -> bool:
            path_str = str(path_obj)
            return "static" not in path_str

        with (
            patch("pathlib.Path.exists", patched_exists),
            patch(
                "rpi_weather_display.models.config.AppConfig.from_yaml", return_value=mock_config
            ),
            patch("rpi_weather_display.utils.logging.setup_logging", return_value=mock_logger),
            patch("logging.getLogger", return_value=mock_logger),
        ):
            WeatherDisplayServer(Path("test_config.yaml"))

            assert mock_logger.warning.call_count >= 1
            assert any(
                "Static files directory not found" in str(call)
                for call in mock_logger.warning.call_args_list
            )

    def test_path_resolver_integration(self) -> None:
        """Test path_resolver integration in server."""
        mock_config = MagicMock()
        mock_config.logging = LoggingConfig(level="INFO")

        mock_app = MagicMock()

        def app_factory() -> FastAPI:
            return mock_app

        with tempfile.TemporaryDirectory() as temp_dir:
            static_dir_path = Path(temp_dir) / "static"
            templates_dir_path = Path(temp_dir) / "templates"
            static_dir_path.mkdir()
            templates_dir_path.mkdir()

            with (
                patch(
                    "rpi_weather_display.models.config.AppConfig.from_yaml",
                    return_value=mock_config,
                ),
                patch("rpi_weather_display.utils.logging.setup_logging", return_value=_mock_logger),
                patch(
                    "rpi_weather_display.utils.path_resolver.get_templates_dir",
                    return_value=templates_dir_path,
                ),
                patch(
                    "rpi_weather_display.utils.path_resolver.get_static_dir",
                    return_value=static_dir_path,
                ),
                patch("rpi_weather_display.server.main.path_resolver.ensure_dir_exists"),
                patch("fastapi.staticfiles.StaticFiles", return_value=MagicMock()),
            ):
                server = WeatherDisplayServer(Path("test_config.yaml"), app_factory=app_factory)

                assert server.template_dir == templates_dir_path
                assert server.static_dir == static_dir_path
                mock_app.mount.assert_called_once()


class TestServerEndpoints:
    """Tests for server HTTP endpoints."""

    def test_server_routes_exist(self, test_server: WeatherDisplayServer) -> None:
        """Test that all required routes are set up."""
        client = TestClient(test_server.app)

        response = client.get("/")
        assert response.status_code == 200

        routes = [str(route) for route in test_server.app.routes]

        assert any("path='/'," in route for route in routes), "Root route not found"
        assert any("path='/render'," in route for route in routes), "Render route not found"
        assert any("path='/weather'," in route for route in routes), "Weather route not found"
        assert any("path='/preview'," in route for route in routes), "Preview route not found"
        assert any("path='/memory'," in route for route in routes), "Memory route not found"

    @pytest.mark.asyncio()
    async def test_render_endpoint(self, test_server: WeatherDisplayServer) -> None:
        """Test the render endpoint."""
        mock_weather_data = MagicMock()
        test_server.api_client.get_weather_data = AsyncMock(return_value=mock_weather_data)

        tmp_path = create_temp_file(suffix=".png")

        try:
            test_server.renderer.render_weather_image = AsyncMock(return_value=tmp_path)
            mock_response = Response(content=b"test image data", media_type="image/png")

            with patch("fastapi.responses.FileResponse", return_value=mock_response):
                client = TestClient(test_server.app)

                battery_info = {
                    "level": 85,
                    "state": "full",
                    "voltage": 3.9,
                    "current": 0.5,
                    "temperature": 25.0,
                }

                response = client.post("/render", json={"battery": battery_info})

                assert response.status_code == 200

                test_server.api_client.get_weather_data.assert_called_once()
                test_server.renderer.render_weather_image.assert_called_once()

                args, _ = test_server.renderer.render_weather_image.call_args
                battery_status = args[1]
                assert battery_status.level == 85
                assert battery_status.state == BatteryState.FULL
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    @pytest.mark.asyncio()
    async def test_render_endpoint_error(self, test_server: WeatherDisplayServer) -> None:
        """Test error handling in the render endpoint."""
        test_server.api_client.get_weather_data = AsyncMock(side_effect=Exception("API error"))

        client = TestClient(test_server.app)

        battery_info = {
            "level": 85,
            "state": "full",
            "voltage": 3.9,
            "current": 0.5,
            "temperature": 25.0,
        }

        response = client.post("/render", json={"battery": battery_info})

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "API error" in data["detail"]

    @pytest.mark.asyncio()
    async def test_weather_endpoint(self, test_server: WeatherDisplayServer) -> None:
        """Test the weather endpoint."""
        mock_data_path = Path(__file__).parent.parent / "data" / "mock_weather_response.json"
        with mock_data_path.open() as f:
            weather_json = json.load(f)

        from datetime import datetime

        weather_json["air_pollution"] = None
        weather_json["last_updated"] = datetime.now().isoformat()

        mock_weather_data = WeatherData(**weather_json)

        test_server.api_client.get_weather_data = AsyncMock(return_value=mock_weather_data)

        client = TestClient(test_server.app)
        response = client.get("/weather")

        assert response.status_code == 200
        data = response.json()

        assert "lat" in data
        assert "lon" in data
        assert "current" in data
        assert "hourly" in data
        assert "daily" in data
        assert data["lat"] == 33.749
        assert data["lon"] == -84.388

        test_server.api_client.get_weather_data.assert_called_once()

    @pytest.mark.asyncio()
    async def test_weather_endpoint_error(self, test_server: WeatherDisplayServer) -> None:
        """Test error handling in the weather endpoint."""
        test_server.api_client.get_weather_data = AsyncMock(side_effect=Exception("API error"))

        client = TestClient(test_server.app)
        response = client.get("/weather")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "API error" in data["detail"]

    @pytest.mark.asyncio()
    async def test_preview_endpoint(self, test_server: WeatherDisplayServer) -> None:
        """Test the preview endpoint."""
        mock_weather_data = MagicMock()

        test_server.api_client.get_weather_data = AsyncMock(return_value=mock_weather_data)
        test_server.renderer.generate_html = AsyncMock(return_value="<html>Test</html>")

        client = TestClient(test_server.app)
        response = client.get("/preview")

        assert response.status_code == 200
        assert response.text == "<html>Test</html>"

        test_server.api_client.get_weather_data.assert_called_once()
        test_server.renderer.generate_html.assert_called_once()

        battery_status = test_server.renderer.generate_html.call_args[0][1]
        assert battery_status.level == 85
        assert battery_status.state == BatteryState.FULL

    @pytest.mark.asyncio()
    async def test_preview_endpoint_error(self, test_server: WeatherDisplayServer) -> None:
        """Test error handling in the preview endpoint."""
        test_server.api_client.get_weather_data = AsyncMock(side_effect=Exception("API error"))

        client = TestClient(test_server.app)
        response = client.get("/preview")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "API error" in data["detail"]

    def test_memory_endpoint(self, test_server: WeatherDisplayServer) -> None:
        """Test the /memory endpoint."""
        client = TestClient(test_server.app)

        with patch("rpi_weather_display.server.main.memory_profiler") as mock_profiler:
            mock_profiler.get_report.return_value = {
                "current": {
                    "rss_mb": 150.0,
                    "vms_mb": 300.0,
                    "percent": 5.0,
                    "available_system_mb": 2000.0,
                },
                "timestamp": 1234567890.0,
            }

            response = client.get("/memory")

            assert response.status_code == 200
            data = response.json()
            assert data["current"]["rss_mb"] == 150.0
            assert data["timestamp"] == 1234567890.0
            mock_profiler.get_report.assert_called_once()

    @pytest.mark.asyncio()
    async def test_handle_render_direct(self, test_server_with_mocks: WeatherDisplayServer) -> None:
        """Test the _handle_render method directly."""
        mock_weather_data = MagicMock()
        test_server_with_mocks.api_client.get_weather_data = AsyncMock(
            return_value=mock_weather_data
        )
        test_server_with_mocks.renderer.render_weather_image = AsyncMock()

        mock_temp_path = Path("/var/folders/safe/mock/weather.png")

        request = RenderRequest(
            battery=BatteryInfo(
                level=85, state=BatteryState.FULL.value, voltage=3.9, current=0.5, temperature=25.0
            )
        )

        mock_response = MagicMock()

        with (
            patch(
                "rpi_weather_display.server.main.path_resolver.get_temp_file",
                return_value=mock_temp_path,
            ),
            patch("rpi_weather_display.server.main.FileResponse", return_value=mock_response),
        ):
            background_tasks = BackgroundTasks()
            response = await test_server_with_mocks._handle_render(request, background_tasks)

            assert response == mock_response

    @pytest.mark.asyncio()
    async def test_handle_render_error(self, test_server_with_mocks: WeatherDisplayServer) -> None:
        """Test error handling in _handle_render."""
        test_server_with_mocks.logger = _mock_logger
        test_server_with_mocks.api_client.get_weather_data = AsyncMock(
            side_effect=Exception("Test error")
        )

        request = RenderRequest(
            battery=BatteryInfo(level=85, state="full", voltage=3.9, current=0.5, temperature=25.0)
        )

        _mock_logger.reset_mock()

        with patch(
            "rpi_weather_display.server.main.get_error_location", return_value="test_location"
        ):
            background_tasks = BackgroundTasks()
            with pytest.raises(HTTPException) as excinfo:
                await test_server_with_mocks._handle_render(request, background_tasks)

            _mock_logger.error.assert_called_once_with(
                "Error rendering weather image [test_location]: Test error"
            )

            assert excinfo.value.status_code == 500
            assert "Test error" in excinfo.value.detail

    @pytest.mark.asyncio()
    async def test_handle_weather_direct(
        self, test_server_with_mocks: WeatherDisplayServer
    ) -> None:
        """Test the _handle_weather method directly."""
        mock_weather_data = MagicMock()
        mock_weather_data.model_dump.return_value = {"test": "data"}

        test_server_with_mocks.api_client.get_weather_data = AsyncMock(
            return_value=mock_weather_data
        )

        result = await test_server_with_mocks._handle_weather()

        assert result == mock_weather_data

    @pytest.mark.asyncio()
    async def test_handle_weather_error(self, test_server_with_mocks: WeatherDisplayServer) -> None:
        """Test error handling in _handle_weather."""
        test_server_with_mocks.api_client.get_weather_data = AsyncMock(
            side_effect=Exception("Test error")
        )

        with pytest.raises(HTTPException) as excinfo:
            await test_server_with_mocks._handle_weather()

        assert excinfo.value.status_code == 500
        assert "Test error" in excinfo.value.detail


class TestServerLifecycle:
    """Tests for server lifecycle management."""

    @pytest.mark.asyncio()
    async def test_lifespan_startup_shutdown(self) -> None:
        """Test lifespan startup and shutdown."""
        app = FastAPI()

        with (
            patch("rpi_weather_display.server.main.memory_profiler") as mock_memory_profiler,
            patch("rpi_weather_display.server.main.browser_manager") as mock_browser_manager,
        ):
            mock_memory_profiler.get_report.return_value = {"current": {"rss_mb": 100.0}}
            mock_browser_manager.cleanup = AsyncMock()

            async with lifespan(app):
                mock_memory_profiler.set_baseline.assert_called_once()

            mock_memory_profiler.get_report.assert_called_once()
            mock_browser_manager.cleanup.assert_called_once()

    @pytest.mark.asyncio()
    async def test_lifespan_with_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test lifespan logging."""
        app = FastAPI()

        with (
            patch("rpi_weather_display.server.main.memory_profiler") as mock_memory_profiler,
            patch("rpi_weather_display.server.main.browser_manager") as mock_browser_manager,
            caplog.at_level(logging.INFO),
        ):
            mock_memory_profiler.get_report.return_value = {"test": "report"}
            mock_browser_manager.cleanup = AsyncMock()

            async with lifespan(app):
                pass

            assert "Starting Weather Display Server" in caplog.text
            assert "Shutting down Weather Display Server" in caplog.text
            assert "Final memory report: {'test': 'report'}" in caplog.text

    @pytest.mark.asyncio()
    async def test_handle_render_memory_growth_warning(
        self, test_server_with_mocks: WeatherDisplayServer, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test memory growth warning during render."""
        mock_api_client = Mock()
        mock_api_client.get_weather_data = AsyncMock(return_value=MagicMock())
        test_server_with_mocks.api_client = mock_api_client

        mock_renderer = Mock()
        mock_renderer.render_weather_image = AsyncMock()
        test_server_with_mocks.renderer = mock_renderer

        request = RenderRequest(
            battery=BatteryInfo(
                level=80,
                state="discharging",
                voltage=3.7,
                current=0.5,
                temperature=25.0,
            )
        )

        with (
            patch("rpi_weather_display.server.main.memory_profiler") as mock_profiler,
            patch("rpi_weather_display.server.main.path_resolver") as mock_resolver,
            patch("rpi_weather_display.server.main.BackgroundTasks") as mock_bg_tasks,
            caplog.at_level(logging.WARNING),
        ):
            mock_profiler.check_memory_growth.return_value = True
            mock_profiler.record_snapshot = Mock()

            mock_temp_path = MagicMock()
            mock_resolver.get_temp_file.return_value = mock_temp_path

            mock_bg_instance = MagicMock()
            mock_bg_tasks.return_value = mock_bg_instance

            await test_server_with_mocks._handle_render(request, mock_bg_instance)

            mock_profiler.check_memory_growth.assert_called_once_with(
                threshold_mb=SERVER_MEMORY_GROWTH_THRESHOLD_MB
            )
            assert "Excessive memory growth detected during rendering" in caplog.text

    @pytest.mark.asyncio()
    async def test_cleanup_temp_file_error(
        self, test_server_with_mocks: WeatherDisplayServer, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test cleanup error handling in background task."""
        mock_path = MagicMock()
        mock_path.unlink.side_effect = Exception("Cleanup failed")

        def cleanup_temp_file() -> None:
            """Clean up temporary file after response is sent."""
            try:
                mock_path.unlink(missing_ok=True)
            except Exception as clean_e:
                test_server_with_mocks.logger.warning(
                    f"Failed to clean up temp file {mock_path}: {clean_e}"
                )

        with caplog.at_level(logging.WARNING):
            cleanup_temp_file()

            assert "Failed to clean up temp file" in caplog.text
            assert "Cleanup failed" in caplog.text

    def test_run_method(self, test_server: WeatherDisplayServer) -> None:
        """Test the run method."""
        with patch("uvicorn.run") as mock_run:
            test_server.run(host=DEFAULT_SERVER_HOST, port=9000)

            mock_run.assert_called_once_with(test_server.app, host=DEFAULT_SERVER_HOST, port=9000)

    def test_run_method_default_values(self, test_server: WeatherDisplayServer) -> None:
        """Test the run method with default values."""
        with patch("uvicorn.run") as mock_run:
            test_server.config.server.port = 8080

            test_server.run()

            args, kwargs = mock_run.call_args
            assert args[0] == test_server.app
            assert kwargs["port"] == 8080

    def test_run_method_parameters(self, test_server_with_mocks: WeatherDisplayServer) -> None:
        """Test server run method with various parameter combinations."""
        test_server_with_mocks.config.server.url = f"http://{DEFAULT_SERVER_HOST}"
        test_server_with_mocks.config.server.port = 8888

        with patch("uvicorn.run") as mock_uvicorn:
            # Test with default parameters
            test_server_with_mocks.run()
            mock_uvicorn.assert_called_once_with(
                test_server_with_mocks.app, host=DEFAULT_SERVER_HOST, port=8888
            )
            mock_uvicorn.reset_mock()

            # Test with explicit host and port
            test_server_with_mocks.run(host="localhost", port=9999)
            mock_uvicorn.assert_called_once_with(
                test_server_with_mocks.app, host="localhost", port=9999
            )
            mock_uvicorn.reset_mock()

            # Test with only host parameter
            test_server_with_mocks.run(host="localhost")
            mock_uvicorn.assert_called_once_with(
                test_server_with_mocks.app, host="localhost", port=8888
            )
            mock_uvicorn.reset_mock()

            # Test with only port parameter
            test_server_with_mocks.run(port=7777)
            mock_uvicorn.assert_called_once_with(
                test_server_with_mocks.app, host=DEFAULT_SERVER_HOST, port=7777
            )


class TestServerConfiguration:
    """Tests for server configuration and main function."""

    def test_main_function(self) -> None:
        """Test the main function."""
        with (
            patch("argparse.ArgumentParser.parse_args") as mock_parse_args,
            patch("pathlib.Path.exists", return_value=True),
            patch("rpi_weather_display.server.main.WeatherDisplayServer") as mock_server,
        ):
            mock_args = MagicMock()
            mock_args.config = Path(f"/etc/{CLIENT_CACHE_DIR_NAME}/config.yaml")
            mock_args.host = DEFAULT_SERVER_HOST
            mock_args.port = 9000
            mock_parse_args.return_value = mock_args

            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance

            main()

            mock_server.assert_called_once_with(mock_args.config)
            mock_server_instance.run.assert_called_once_with(host=DEFAULT_SERVER_HOST, port=9000)

    def test_main_function_config_not_found(self) -> None:
        """Test the main function when config file is not found."""
        with (
            patch("argparse.ArgumentParser.parse_args") as mock_parse_args,
            patch("pathlib.Path.exists", return_value=False),
            patch("builtins.print") as mock_print,
            patch("rpi_weather_display.server.main.WeatherDisplayServer") as mock_server,
        ):
            mock_args = MagicMock()
            mock_args.config = Path(f"/etc/{CLIENT_CACHE_DIR_NAME}/config.yaml")
            mock_parse_args.return_value = mock_args

            mock_instance = MagicMock()
            mock_server.return_value = mock_instance

            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1

            mock_print.assert_called()
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Configuration Error" in str(call) for call in print_calls)

    def test_main_function_with_config_path(self) -> None:
        """Test the main function when a config path is provided."""
        mock_config_path = MagicMock()
        mock_config_path.exists.return_value = True

        mock_server_instance = MagicMock()

        with (
            patch("argparse.ArgumentParser.parse_args") as mock_parse_args,
            patch(
                "rpi_weather_display.server.main.WeatherDisplayServer",
                return_value=mock_server_instance,
            ) as mock_server_class,
            patch(
                "rpi_weather_display.server.main.validate_config_path",
                return_value=mock_config_path,
            ),
        ):
            mock_args = MagicMock()
            mock_args.config = mock_config_path
            mock_args.host = "user-host"
            mock_args.port = 1234
            mock_parse_args.return_value = mock_args

            main()

            mock_server_class.assert_called_once_with(mock_config_path)
            mock_server_instance.run.assert_called_once_with(host="user-host", port=1234)

    def test_main_function_no_config_found(self) -> None:
        """Test the main function when no config is provided and default config is found."""
        mock_path = MagicMock()

        with (
            patch("argparse.ArgumentParser.parse_args") as mock_parse_args,
            patch("rpi_weather_display.server.main.validate_config_path", return_value=mock_path),
            patch("rpi_weather_display.server.main.WeatherDisplayServer") as mock_server,
        ):
            mock_args = MagicMock()
            mock_args.config = None
            mock_args.host = None
            mock_args.port = None
            mock_parse_args.return_value = mock_args

            mock_path.exists.return_value = True

            main()

            mock_server.assert_called_once_with(mock_path)

    def test_main_function_no_config(self) -> None:
        """Test the main function when no config is provided and no default config is found."""
        with (
            patch("argparse.ArgumentParser.parse_args") as mock_parse_args,
            patch("rpi_weather_display.server.main.validate_config_path") as mock_validate,
            patch("builtins.print") as mock_print,
            patch("rpi_weather_display.server.main.WeatherDisplayServer") as mock_server,
        ):
            mock_args = MagicMock()
            mock_args.config = None
            mock_args.host = None
            mock_args.port = None
            mock_parse_args.return_value = mock_args

            mock_validate.side_effect = ConfigFileNotFoundError(
                "Configuration file not found: /mock/path/config.yaml",
                {"path": "/mock/path/config.yaml"},
            )

            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1

            mock_validate.assert_called_once_with(None)

            mock_print.assert_called()
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Configuration Error" in str(call) for call in print_calls)

            mock_print.assert_any_call(
                "Configuration Error: Configuration file not found: /mock/path/config.yaml - Details: {'path': '/mock/path/config.yaml'}"
            )

            mock_server.assert_not_called()

    def test_validate_config_path_not_found(self) -> None:
        """Test that validate_config_path raises ConfigFileNotFoundError when file not found."""
        with patch("pathlib.Path.exists", return_value=False):
            test_path = Path("/test/config.yaml")

            with patch(
                "rpi_weather_display.utils.path_utils.path_resolver.get_config_path",
                return_value=test_path,
            ):
                with pytest.raises(ConfigFileNotFoundError) as excinfo:
                    validate_config_path(None)

                assert "/test/config.yaml" in str(excinfo.value)
                assert excinfo.value.details["path"] == "/test/config.yaml"

    def test_validate_config_path_explicit(self) -> None:
        """Test that validate_config_path works with explicit path."""
        with patch("pathlib.Path.exists", return_value=False):
            non_existent_path = Path("/fake/path.yaml")

            with pytest.raises(ConfigFileNotFoundError) as excinfo:
                validate_config_path(non_existent_path)

            assert "/fake/path.yaml" in str(excinfo.value)
            assert excinfo.value.details["path"] == "/fake/path.yaml"

    def test_validate_config_path_search_locations(self) -> None:
        """Test that validate_config_path includes search locations in error for None paths."""
        with patch("pathlib.Path.exists", return_value=False):
            auto_path = Path("/auto/config.yaml")
            with patch(
                "rpi_weather_display.utils.path_utils.path_resolver.get_config_path",
                return_value=auto_path,
            ):
                with pytest.raises(ConfigFileNotFoundError) as excinfo:
                    validate_config_path(None)

                assert "Searched in the following locations:" in str(excinfo.value)
                assert excinfo.value.details["searched_locations"] is not None
                assert len(excinfo.value.details["searched_locations"]) > 0

            explicit_path = Path("/explicit/config.yaml")
            with pytest.raises(ConfigFileNotFoundError) as excinfo:
                validate_config_path(explicit_path)

            assert "Searched in the following locations:" not in str(excinfo.value)
            assert excinfo.value.details["searched_locations"] is None


class TestStaticFiles:
    """Tests for static file handling."""

    def test_alt_static_dir(self) -> None:
        """Test alternative static directory path."""
        mock_app = MagicMock()

        def app_factory() -> FastAPI:
            return mock_app

        mock_config = MagicMock()
        mock_config.logging = LoggingConfig(level="INFO")

        mock_static_files = MagicMock()
        alt_static_dir = Path(f"/etc/{CLIENT_CACHE_DIR_NAME}/static")

        mock_path_resolver = MagicMock()
        mock_path_resolver.get_static_dir.return_value = alt_static_dir

        def custom_dir_check(directory: Path | str) -> bool:
            return True

        with (
            patch(
                "rpi_weather_display.models.config.AppConfig.from_yaml", return_value=mock_config
            ),
            patch("rpi_weather_display.utils.logging.setup_logging", return_value=MagicMock()),
            patch("fastapi.staticfiles.StaticFiles", return_value=mock_static_files),
            patch("rpi_weather_display.utils.path_resolver", mock_path_resolver),
            patch("rpi_weather_display.utils.file_utils.dir_exists", side_effect=custom_dir_check),
        ):
            WeatherDisplayServer(Path("test_config.yaml"), app_factory=app_factory)

            mock_app.mount.assert_called_once()

            call_args = mock_app.mount.call_args[0]
            assert call_args[0] == "/static"

    def test_static_files_not_found_detailed(self) -> None:
        """Test when static files directory not found with detailed mocking."""
        mock_config = MagicMock()
        mock_config.logging = LoggingConfig(level="INFO")

        mock_logger = MagicMock()
        mock_app = MagicMock()

        def app_factory() -> FastAPI:
            return mock_app

        with tempfile.TemporaryDirectory() as temp_dir:
            test_templates_dir = Path(temp_dir) / "templates"
            test_templates_dir.mkdir()
            nonexistent_static_dir = "/nonexistent/static/dir"

            with (
                patch(
                    "rpi_weather_display.models.config.AppConfig.from_yaml",
                    return_value=mock_config,
                ),
                patch("rpi_weather_display.utils.logging.setup_logging", return_value=_mock_logger),
                patch(
                    "rpi_weather_display.utils.path_resolver.get_templates_dir",
                    return_value=test_templates_dir,
                ),
                patch(
                    "rpi_weather_display.utils.path_resolver.get_static_dir",
                    return_value=Path(nonexistent_static_dir),
                ),
                patch("rpi_weather_display.server.main.path_resolver.ensure_dir_exists"),
                patch(
                    "rpi_weather_display.server.main.path_resolver.normalize_path"
                ) as mock_normalize,
            ):
                mock_path = MagicMock()
                mock_path.exists.return_value = False
                mock_normalize.return_value = mock_path

                server = WeatherDisplayServer(Path("test_config.yaml"), app_factory=app_factory)

                server.logger = mock_logger
                mock_logger.reset_mock()

                server._setup_static_files()

                warning_message = (
                    f"Static files directory not found at {Path(nonexistent_static_dir)}. "
                    "Some resources may not load correctly."
                )
                mock_logger.warning.assert_called_with(warning_message)

                mock_app.mount.assert_not_called()
