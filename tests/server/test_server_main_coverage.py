"""Tests for improving coverage of the server main module."""

# ^ Ignores "Use of assert detected" and "protected-access" in test files, which are common in tests
# pyright: reportPrivateUsage=false, reportFunctionMemberAccess=false, reportUnknownVariableType=false
# pyright: reportGeneralTypeIssues=false

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import BackgroundTasks, FastAPI, Response

from rpi_weather_display.constants import DEFAULT_SERVER_HOST
from rpi_weather_display.exceptions import ConfigFileNotFoundError
from rpi_weather_display.models.config import LoggingConfig
from rpi_weather_display.models.system import BatteryState
from rpi_weather_display.server.main import (
    BatteryInfo,
    RenderRequest,
    WeatherDisplayServer,
)
from rpi_weather_display.utils.path_utils import path_resolver


def test_cache_dir_fallback() -> None:
    """Test the cache_dir fallback assignment."""
    # Create a proper mock config
    mock_config = MagicMock()
    mock_config.logging = LoggingConfig(level="INFO")

    # Set server.cache_dir to None to trigger the fallback
    mock_config.server.cache_dir = None

    # Create a mock path resolver with a fake cache_dir
    mock_cache_dir = Path("/mock/cache/dir")

    # Create app factory that returns a mock app
    mock_app = MagicMock()

    def app_factory() -> FastAPI:
        """Create a mock FastAPI app for testing."""
        return mock_app

    with (
        patch("rpi_weather_display.models.config.AppConfig.from_yaml", return_value=mock_config),
        patch(
            "rpi_weather_display.utils.path_resolver.get_templates_dir",
            return_value=Path("/test/templates"),
        ),
        patch(
            "rpi_weather_display.utils.path_resolver.get_static_dir",
            return_value=Path("/test/static"),
        ),
        patch("rpi_weather_display.server.main.path_resolver.cache_dir", mock_cache_dir),
        patch("rpi_weather_display.server.main.path_resolver.ensure_dir_exists"),
        patch("rpi_weather_display.server.main.FileCache", return_value=MagicMock()),
        patch("pathlib.Path.exists", return_value=True),
        patch("rpi_weather_display.utils.file_utils.dir_exists", return_value=True),
        patch("os.path.isdir", return_value=True),  # Add patch for os.path.isdir
    ):
        # Create server with mock app factory
        server = WeatherDisplayServer(Path("test_config.yaml"), app_factory=app_factory)

        # Verify the cache_dir was set from path_resolver.cache_dir
        assert server.cache_dir == mock_cache_dir


def test_main_function_with_config_path() -> None:
    """Test the main function when a config path is provided."""
    mock_config_path = MagicMock()
    mock_config_path.exists.return_value = True

    # Mock WeatherDisplayServer
    mock_server_instance = MagicMock()

    with (
        patch("argparse.ArgumentParser.parse_args") as mock_parse_args,
        patch(
            "rpi_weather_display.server.main.WeatherDisplayServer",
            return_value=mock_server_instance,
        ) as mock_server_class,
    ):
        # Configure mock args with explicit config path
        mock_args = MagicMock()
        mock_args.config = mock_config_path
        mock_args.host = "user-host"
        mock_args.port = 1234
        mock_parse_args.return_value = mock_args

        # Call main function
        from rpi_weather_display.server.main import main

        main()

        # Verify server was created with the provided config path
        mock_server_class.assert_called_once_with(mock_config_path)

        # Verify run was called with the provided host and port
        mock_server_instance.run.assert_called_once_with(host="user-host", port=1234)


def test_main_function_no_config_found() -> None:
    """Test the main function when no config is provided and default config is found."""
    mock_path = MagicMock()

    with (
        patch("argparse.ArgumentParser.parse_args") as mock_parse_args,
        patch(
            "rpi_weather_display.server.main.path_resolver.get_config_path", return_value=mock_path
        ),
        patch(
            "rpi_weather_display.server.main.path_resolver.user_config_dir",
            Path("/mock/user/config"),
        ),
        patch(
            "rpi_weather_display.server.main.path_resolver.system_config_dir",
            Path("/mock/system/config"),
        ),
        patch(
            "rpi_weather_display.server.main.path_resolver.project_root", Path("/mock/project/root")
        ),
        patch("pathlib.Path.cwd", return_value=Path("/mock/cwd")),
        patch("builtins.print"),
        patch("rpi_weather_display.server.main.WeatherDisplayServer") as mock_server,
    ):
        # Configure mock args with config=None to trigger the path resolver path
        mock_args = MagicMock()
        mock_args.config = None
        mock_args.host = None
        mock_args.port = None
        mock_parse_args.return_value = mock_args

        # The path returned SHOULD exist to trigger the success branch
        mock_path.exists.return_value = True

        # Call main function
        from rpi_weather_display.server.main import main

        main()

        # Verify path_resolver.get_config_path was called with "config.yaml"
        path_resolver.get_config_path.assert_called_once_with("config.yaml")

        # Verify server was created with the found config path
        mock_server.assert_called_once_with(mock_path)


def test_main_function_no_config() -> None:
    """Test the main function when no config is provided and no default config is found."""
    with (
        patch("argparse.ArgumentParser.parse_args") as mock_parse_args,
        patch("rpi_weather_display.server.main.validate_config_path") as mock_validate,
        patch("builtins.print") as mock_print,
        patch("rpi_weather_display.server.main.WeatherDisplayServer") as mock_server,
    ):
        # Configure mock args with config=None to trigger the path resolver path
        mock_args = MagicMock()
        mock_args.config = None
        mock_args.host = None
        mock_args.port = None
        mock_parse_args.return_value = mock_args

        # Mock validate_config_path to raise ConfigFileNotFoundError
        mock_validate.side_effect = ConfigFileNotFoundError(
            "Configuration file not found: /mock/path/config.yaml",
            {"path": "/mock/path/config.yaml"}
        )

        # Call main function and expect SystemExit
        from rpi_weather_display.server.main import main

        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 1

        # Verify validate_config_path was called with None
        mock_validate.assert_called_once_with(None)
        
        # Verify error was printed
        mock_print.assert_called()
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert any("Configuration Error" in str(call) for call in print_calls)

        # Verify the correct error message was printed
        mock_print.assert_any_call("Configuration Error: Configuration file not found: /mock/path/config.yaml - Details: {'path': '/mock/path/config.yaml'}")

        # Verify server was not created
        mock_server.assert_not_called()


@pytest.mark.asyncio()
async def test_route_handlers() -> None:
    """Test the route handlers directly."""
    # Create a proper mock config
    mock_config = MagicMock()
    mock_config.logging = LoggingConfig(level="INFO")

    # Create a mock app that we can control
    mock_app = MagicMock()
    registered_routes = {}

    # Override app.get to capture route handlers
    def mock_app_get(path: str) -> callable:
        def decorator(func: callable) -> callable:
            registered_routes[path] = func
            return func

        return decorator

    # Override app.post to capture route handlers
    def mock_app_post(path: str) -> callable:
        def decorator(func: callable) -> callable:
            registered_routes[path] = func
            return func

        return decorator

    # Assign the mocked methods
    mock_app.get = mock_app_get
    mock_app.post = mock_app_post

    def app_factory() -> FastAPI:
        return mock_app

    # Mock browser_manager to prevent async warnings
    mock_browser_manager = MagicMock()
    mock_browser_manager.cleanup = Mock()  # Not AsyncMock since we're not awaiting it

    with (
        patch("rpi_weather_display.server.main.browser_manager", mock_browser_manager),
        patch("rpi_weather_display.models.config.AppConfig.from_yaml", return_value=mock_config),
        patch(
            "rpi_weather_display.utils.path_resolver.get_templates_dir",
            return_value=Path("/test/templates"),
        ),
        patch(
            "rpi_weather_display.utils.path_resolver.get_static_dir",
            return_value=Path("/test/static"),
        ),
        patch("rpi_weather_display.server.main.path_resolver.ensure_dir_exists"),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("os.path.isdir", return_value=True),
        patch("rpi_weather_display.utils.file_utils.dir_exists", return_value=True),
    ):
        # Create server with mock app factory
        server = WeatherDisplayServer(Path("test_config.yaml"), app_factory=app_factory)

        # Test root route
        root_handler = registered_routes["/"]
        response = await root_handler()
        assert response == {"status": "ok", "service": "Weather Display Server"}

        # Mock API client for other endpoints
        server.api_client.get_weather_data = AsyncMock()

        # Test render route
        render_handler = registered_routes["/render"]
        # Patch server._handle_render to avoid implementation details
        server._handle_render = AsyncMock()
        mock_request = MagicMock()
        mock_background_tasks = BackgroundTasks()
        await render_handler(mock_request, mock_background_tasks)
        server._handle_render.assert_called_once_with(mock_request, mock_background_tasks)

        # Test weather route
        weather_handler = registered_routes["/weather"]
        # Patch server._handle_weather to avoid implementation details
        server._handle_weather = AsyncMock()
        await weather_handler()
        server._handle_weather.assert_called_once()

        # Test preview route with mocks for required components
        preview_handler = registered_routes["/preview"]

        # Create mock data
        mock_weather_data = MagicMock()
        mock_html = "<html>Test</html>"

        # Mock dependencies
        server.api_client.get_weather_data = AsyncMock(return_value=mock_weather_data)
        server.renderer.generate_html = AsyncMock(return_value=mock_html)

        # Call the handler
        response = await preview_handler()

        # Verify response
        assert isinstance(response, Response)
        assert response.body == mock_html.encode()

        # Test preview route error handling
        server.api_client.get_weather_data = AsyncMock(side_effect=Exception("API error"))

        # Import modules needed for HTTPException

        from fastapi import HTTPException

        # Call the handler and check for exception
        with pytest.raises(HTTPException) as excinfo:
            await preview_handler()

        # Verify exception details
        assert excinfo.value.status_code == 500
        assert "API error" in excinfo.value.detail


# Create separate tests for the other handler methods
@pytest.mark.asyncio()
async def test_handle_render() -> None:
    """Test the _handle_render method."""
    # Create a proper mock config
    mock_config = MagicMock()
    mock_config.logging = LoggingConfig(level="INFO")

    # Create a mock logger
    mock_logger = MagicMock()

    # Create app factory that returns a mock app
    mock_app = MagicMock()

    def app_factory() -> FastAPI:
        """Create a mock FastAPI app for testing."""
        return mock_app

    with (
        patch("rpi_weather_display.models.config.AppConfig.from_yaml", return_value=mock_config),
        patch(
            "rpi_weather_display.utils.path_resolver.get_templates_dir",
            return_value=Path("/test/templates"),
        ),
        patch(
            "rpi_weather_display.utils.path_resolver.get_static_dir",
            return_value=Path("/test/static"),
        ),
        patch("rpi_weather_display.server.main.path_resolver.ensure_dir_exists"),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("os.path.isdir", return_value=True),
        patch("rpi_weather_display.utils.file_utils.dir_exists", return_value=True),
        patch("rpi_weather_display.server.main.get_error_location", return_value="test_location"),
    ):
        # Create server
        server = WeatherDisplayServer(Path("test_config.yaml"), app_factory=app_factory)

        # Replace the server logger with our mock
        server.logger = mock_logger

        # Mock the API client and renderer
        mock_weather_data = MagicMock()
        server.api_client.get_weather_data = AsyncMock(return_value=mock_weather_data)
        server.renderer.render_weather_image = AsyncMock()

        # Mock path_resolver.get_temp_file
        mock_temp_path = Path("/var/folders/safe/mock/weather.png")  # Use a safer path

        # Create the request object
        request = RenderRequest(
            battery=BatteryInfo(
                level=85, state=BatteryState.FULL.value, voltage=3.9, current=0.5, temperature=25.0
            )
        )

        # Mock FileResponse
        mock_response = MagicMock()

        with (
            patch(
                "rpi_weather_display.server.main.path_resolver.get_temp_file",
                return_value=mock_temp_path,
            ),
            patch("rpi_weather_display.server.main.FileResponse", return_value=mock_response),
        ):
            # Call the method with mock background tasks
            background_tasks = BackgroundTasks()
            response = await server._handle_render(request, background_tasks)

            # Verify the response
            assert response == mock_response

            # Test error handling
            error_msg = "Test error"
            server.api_client.get_weather_data = AsyncMock(side_effect=Exception(error_msg))

            # Reset the logger mock
            mock_logger.reset_mock()

            # Import needed for HTTPException
            from fastapi import HTTPException

            background_tasks = BackgroundTasks()
            with pytest.raises(HTTPException) as excinfo:
                await server._handle_render(request, background_tasks)

            # Verify error was logged
            mock_logger.error.assert_called_once_with(
                f"Error rendering weather image [test_location]: {error_msg}"
            )

            assert excinfo.value.status_code == 500
            assert error_msg in excinfo.value.detail


@pytest.mark.asyncio()
async def test_handle_weather() -> None:
    """Test the _handle_weather method."""
    # Create a proper mock config
    mock_config = MagicMock()
    mock_config.logging = LoggingConfig(level="INFO")

    # Create app factory that returns a mock app
    mock_app = MagicMock()

    def app_factory() -> FastAPI:
        """Create a mock FastAPI app for testing."""
        return mock_app

    with (
        patch("rpi_weather_display.models.config.AppConfig.from_yaml", return_value=mock_config),
        patch(
            "rpi_weather_display.utils.path_resolver.get_templates_dir",
            return_value=Path("/test/templates"),
        ),
        patch(
            "rpi_weather_display.utils.path_resolver.get_static_dir",
            return_value=Path("/test/static"),
        ),
        patch("rpi_weather_display.server.main.path_resolver.ensure_dir_exists"),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("os.path.isdir", return_value=True),
        patch("rpi_weather_display.utils.file_utils.dir_exists", return_value=True),
    ):
        # Create server
        server = WeatherDisplayServer(Path("test_config.yaml"), app_factory=app_factory)

        # Create mock weather data
        mock_weather_data = MagicMock()
        mock_weather_data.model_dump.return_value = {"test": "data"}

        # Mock the API client
        server.api_client.get_weather_data = AsyncMock(return_value=mock_weather_data)

        # Call the method
        result = await server._handle_weather()

        # Verify the result (now returns the model directly)
        assert result == mock_weather_data

        # Test error handling
        server.api_client.get_weather_data = AsyncMock(side_effect=Exception("Test error"))

        # Import needed for HTTPException
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as excinfo:
            await server._handle_weather()

        assert excinfo.value.status_code == 500
        assert "Test error" in excinfo.value.detail


def test_static_files_not_found() -> None:
    """Test when static files directory not found."""
    # Create a proper mock config
    mock_config = MagicMock()
    mock_config.logging = LoggingConfig(level="INFO")

    # Create a mock logger
    mock_logger = MagicMock()

    # Create a mock app
    mock_app = MagicMock()

    def app_factory() -> FastAPI:
        """Create a mock FastAPI app for testing."""
        return mock_app

    # Mock function to return False only for paths containing 'static'
    def mock_exists(path: Path) -> bool:
        return "static" not in str(path)

    def mock_is_dir(path: Path) -> bool:
        # Same behavior as exists for directories
        return "static" not in str(path)

    with (
        patch("rpi_weather_display.models.config.AppConfig.from_yaml", return_value=mock_config),
        patch(
            "rpi_weather_display.utils.path_resolver.get_templates_dir",
            return_value=Path("/test/templates"),
        ),
        patch(
            "rpi_weather_display.utils.path_resolver.get_static_dir",
            return_value=Path("/test/static"),
        ),
        patch("rpi_weather_display.server.main.path_resolver.ensure_dir_exists"),
        # The key difference: static directory doesn't exist
        patch("pathlib.Path.exists", mock_exists),
        patch("pathlib.Path.is_dir", mock_is_dir),
        patch("os.path.isdir", mock_is_dir),  # Add os.path.isdir mock
        patch("rpi_weather_display.utils.file_utils.dir_exists", mock_exists),
    ):
        # Create server
        server = WeatherDisplayServer(Path("test_config.yaml"), app_factory=app_factory)

        # Replace the server's logger with our mock to ensure we capture the warning
        server.logger = mock_logger

        # Force call to _setup_static_files to ensure it logs the warning
        server._setup_static_files()

        # Verify warning was logged about static directory
        mock_logger.warning.assert_any_call(
            f"Static files directory not found at {Path('/test/static')}. "
            "Some resources may not load correctly."
        )

        # Verify app.mount was not called (since the directory doesn't exist)
        mock_app.mount.assert_not_called()


def test_server_run_method() -> None:
    """Test the server run method."""
    # Create a proper mock config with host and port
    mock_config = MagicMock()
    mock_config.logging = LoggingConfig(level="INFO")
    mock_config.server.host = DEFAULT_SERVER_HOST
    mock_config.server.port = 8888

    # Create a mock logger
    mock_logger = MagicMock()

    # Create a mock app
    mock_app = MagicMock()

    def app_factory() -> FastAPI:
        """Create a mock FastAPI app for testing."""
        return mock_app

    # Create a mock for uvicorn
    mock_uvicorn = MagicMock()

    with (
        patch("rpi_weather_display.models.config.AppConfig.from_yaml", return_value=mock_config),
        patch(
            "rpi_weather_display.utils.path_resolver.get_templates_dir",
            return_value=Path("/test/templates"),
        ),
        patch(
            "rpi_weather_display.utils.path_resolver.get_static_dir",
            return_value=Path("/test/static"),
        ),
        patch("rpi_weather_display.server.main.path_resolver.ensure_dir_exists"),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("os.path.isdir", return_value=True),
        patch("rpi_weather_display.utils.file_utils.dir_exists", return_value=True),
        patch("uvicorn.run", mock_uvicorn.run),
    ):
        # Create the server
        server = WeatherDisplayServer(Path("test_config.yaml"), app_factory=app_factory)

        # Replace the server's logger
        server.logger = mock_logger

        # Test run method with default parameters
        server.run()
        mock_uvicorn.run.assert_called_once_with(mock_app, host=DEFAULT_SERVER_HOST, port=8888)
        mock_uvicorn.run.reset_mock()

        # Test with explicit host and port parameters (using 127.0.0.1 instead of 0.0.0.0)
        server.run(host=DEFAULT_SERVER_HOST, port=9999)
        mock_uvicorn.run.assert_called_once_with(mock_app, host=DEFAULT_SERVER_HOST, port=9999)
        mock_uvicorn.run.reset_mock()

        # Test with only host parameter
        server.run(host="localhost")
        mock_uvicorn.run.assert_called_once_with(mock_app, host="localhost", port=8888)
        mock_uvicorn.run.reset_mock()

        # Test with only port parameter
        server.run(port=7777)
        mock_uvicorn.run.assert_called_once_with(mock_app, host=DEFAULT_SERVER_HOST, port=7777)


@pytest.fixture()
def test_server() -> WeatherDisplayServer:
    """Create a test server instance with full import coverage."""
    # Create a mock app
    mock_app = MagicMock()

    def app_factory() -> FastAPI:
        """Create a mock FastAPI app for testing."""
        return mock_app

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("os.path.isdir", return_value=True),
        patch("rpi_weather_display.utils.file_utils.dir_exists", return_value=True),
    ):
        # Create mock config
        mock_config = MagicMock()
        mock_config.logging = LoggingConfig(level="INFO")
        mock_config.server.port = 8000

        with (
            patch(
                "rpi_weather_display.models.config.AppConfig.from_yaml", return_value=mock_config
            ),
            patch(
                "rpi_weather_display.utils.path_resolver.get_templates_dir",
                return_value=Path("/test/templates"),
            ),
            patch(
                "rpi_weather_display.utils.path_resolver.get_static_dir",
                return_value=Path("/test/static"),
            ),
            patch("rpi_weather_display.server.main.path_resolver.ensure_dir_exists"),
        ):
            server = WeatherDisplayServer(Path("test_config.yaml"), app_factory=app_factory)

    return server
