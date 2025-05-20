"""Tests for server main module using path_resolver."""
# ruff: noqa: S101, RUF009
# ^ Ignores "Use of assert detected" and "protected-access" in test files, which are common in tests
# pyright: reportPrivateUsage=false, reportFunctionMemberAccess=false, reportUnknownVariableType=false
# pyright: reportGeneralTypeIssues=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUnknownArgumentType=false

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Response

from rpi_weather_display.models.config import LoggingConfig
from rpi_weather_display.models.system import BatteryState
from rpi_weather_display.server.main import (
    BatteryInfo,
    RenderRequest,
    WeatherDisplayServer,
)


def test_path_resolver_integration() -> None:
    """Test the integration of path_resolver in server."""
    # Create a proper mock config
    mock_config = MagicMock()
    mock_config.logging = LoggingConfig(level="INFO")

    # Create a mock logger to capture information
    mock_logger = MagicMock()

    # Create app factory that returns a mock app
    mock_app = MagicMock()

    def app_factory() -> FastAPI:
        """Create a mock FastAPI app for testing."""
        return mock_app

    # Mock StaticFiles to avoid directory check
    mock_static_files = MagicMock()
    
    # Create a temporary directory for tests
    import tempfile
    test_static_dir = tempfile.mkdtemp()
    test_templates_dir = tempfile.mkdtemp()
    
    try:
        # Must create real directories for the test
        static_dir_path = Path(test_static_dir)
        templates_dir_path = Path(test_templates_dir)
        
        with (
            patch("rpi_weather_display.models.config.AppConfig.from_yaml", return_value=mock_config),
            patch("rpi_weather_display.utils.logging.setup_logging", return_value=mock_logger),
            patch(
                "rpi_weather_display.utils.path_resolver.get_templates_dir",
                return_value=templates_dir_path,
            ),
            patch(
                "rpi_weather_display.utils.path_resolver.get_static_dir",
                return_value=static_dir_path,
            ),
            patch("rpi_weather_display.server.main.path_resolver.ensure_dir_exists"),
            patch("fastapi.staticfiles.StaticFiles", return_value=mock_static_files),
        ):
            # Create server with mock app factory
            server = WeatherDisplayServer(
                Path("test_config.yaml"), app_factory=app_factory
            )
            
            # Verify the server uses path_resolver methods
            assert server.template_dir == templates_dir_path
            assert server.static_dir == static_dir_path
            
            # Verify that mount was called for the static files
            mock_app.mount.assert_called_once()
    finally:
        # Cleanup temporary directories
        import shutil
        shutil.rmtree(test_static_dir, ignore_errors=True)
        shutil.rmtree(test_templates_dir, ignore_errors=True)


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

    # Create a temporary directory for tests
    import tempfile
    test_static_dir = tempfile.mkdtemp()
    test_templates_dir = tempfile.mkdtemp()
    
    try:
        with (
            patch("rpi_weather_display.models.config.AppConfig.from_yaml", return_value=mock_config),
            patch("rpi_weather_display.utils.logging.setup_logging", return_value=MagicMock()),
            patch(
                "rpi_weather_display.utils.path_resolver.get_templates_dir",
                return_value=Path(test_templates_dir),
            ),
            patch(
                "rpi_weather_display.utils.path_resolver.get_static_dir",
                return_value=Path(test_static_dir),
            ),
            patch("rpi_weather_display.server.main.path_resolver.cache_dir", mock_cache_dir),
            patch("rpi_weather_display.server.main.path_resolver.ensure_dir_exists"),
            patch("fastapi.staticfiles.StaticFiles", return_value=MagicMock()),
        ):
            # Create server with mock app factory
            server = WeatherDisplayServer(Path("test_config.yaml"), app_factory=app_factory)

            # Verify the cache_dir was set from path_resolver.cache_dir
            assert server.cache_dir == mock_cache_dir
    finally:
        # Cleanup temporary directories
        import shutil
        shutil.rmtree(test_static_dir, ignore_errors=True)
        shutil.rmtree(test_templates_dir, ignore_errors=True)


def test_main_function_with_config_path() -> None:
    """Test the main function when a config path is provided."""
    mock_config_path = MagicMock()
    mock_config_path.exists.return_value = True
    
    # Mock WeatherDisplayServer
    mock_server_instance = MagicMock()

    with (
        patch("argparse.ArgumentParser.parse_args") as mock_parse_args,
        patch("rpi_weather_display.server.main.WeatherDisplayServer", return_value=mock_server_instance) as mock_server_class,
        patch("rpi_weather_display.server.main.validate_config_path", return_value=mock_config_path),
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
        patch("rpi_weather_display.server.main.validate_config_path", return_value=mock_path),
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

        # Verify server was created with the found config path
        mock_server.assert_called_once_with(mock_path)


def test_validate_config_path_in_tests() -> None:
    """Test that validate_config_path doesn't exit in test environment."""
    # Let's patch the actual validate_config_path for test observation
    with (
        patch("pathlib.Path.exists", return_value=False),
        patch("sys.exit") as mock_exit,
        patch("builtins.print"),
    ):
        # Create a non-existent path that we can check with our patched Path.exists
        test_path = Path("/test/config.yaml")
        
        # From our docstring analysis, validate_config_path does the following:
        # 1. If path is None, it uses path_resolver.get_config_path() (we'll mock that)
        # 2. It checks if path exists, and if not, prints error messages
        # 3. In a test environment, it returns the path without exiting
        # 4. In production, it would exit with code 1
        
        # Create a test double for path_resolver.get_config_path
        with patch("rpi_weather_display.utils.path_utils.path_resolver.get_config_path",
                  return_value=test_path):
            
            # Make sure we recognize we're in a test environment
            with patch("inspect.stack") as mock_stack:
                mock_frame = MagicMock()
                mock_frame.filename = "/path/containing/pytest/file.py"
                mock_stack.return_value = [mock_frame]
                
                # Now import and use the real function
                from rpi_weather_display.utils.path_utils import validate_config_path
                
                # Call with None to test auto-resolution
                result = validate_config_path(None)
                
                # Should return the path even though it doesn't exist
                assert result == test_path
                
                # Should NOT have called sys.exit in a test environment
                mock_exit.assert_not_called()


def test_validate_config_path_exit_behavior() -> None:
    """Test that validate_config_path calls sys.exit when not in a test environment."""
    # We'll replace the entire in_test check function to control behavior
    from rpi_weather_display.utils.path_utils import validate_config_path
    
    # Create a version of the function with mocked test environment detection
    with patch("inspect.stack") as mock_stack:
        # First, make it return non-test environment
        mock_stack.return_value = []  # No frames at all, so 'pytest' won't be found
        
        # Also mock sys.exit and Path.exists
        with patch("sys.exit") as mock_exit, patch("pathlib.Path.exists", return_value=False):
            # Test with a non-existent path in "production" mode
            non_existent_path = Path("/fake/path.yaml")  
            
            # This should try to call sys.exit(1) due to our mocked production environment
            validate_config_path(non_existent_path)
            
            # Verify sys.exit was called as expected
            mock_exit.assert_called_once_with(1)


def test_validate_config_path_search_locations() -> None:
    """Test that validate_config_path shows search locations only for None paths."""
    # For this test, we need to patch print and check what's printed
    with patch("builtins.print") as mock_print:
        from rpi_weather_display.utils.path_utils import validate_config_path
        
        # Make all paths appear not to exist
        with patch("pathlib.Path.exists", return_value=False):
            # Make sure we're in a test env so sys.exit isn't called
            with patch("inspect.stack") as mock_stack:
                # Force test environment detection
                mock_frame = MagicMock()
                mock_frame.filename = "/path/with/pytest/test_file.py"
                mock_stack.return_value = [mock_frame]
                
                # Test auto-resolved path (None)
                auto_path = Path("/auto/config.yaml")
                with patch("rpi_weather_display.utils.path_utils.path_resolver.get_config_path", 
                           return_value=auto_path):
                    # Call with None to use auto-resolution
                    validate_config_path(None)
                    
                    # Should have printed search locations
                    printed_messages = [call[0][0] for call in mock_print.call_args_list]
                    assert any("Searched in the following locations:" in msg for msg in printed_messages)
                
                # Reset the mock_print
                mock_print.reset_mock()
                
                # Test explicit path
                explicit_path = Path("/explicit/config.yaml")
                validate_config_path(explicit_path)
                
                # Should NOT have printed search locations
                printed_messages = [call[0][0] for call in mock_print.call_args_list]
                assert not any("Searched in the following locations:" in msg for msg in printed_messages)


# End of validate_config_path tests


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
    
    # Create a temporary directory for templates
    import tempfile
    test_templates_dir = tempfile.mkdtemp()
    nonexistent_static_dir = "/nonexistent/static/dir"
    
    try:
        with (
            patch("rpi_weather_display.models.config.AppConfig.from_yaml", return_value=mock_config),
            patch("rpi_weather_display.utils.logging.setup_logging", return_value=mock_logger),
            patch(
                "rpi_weather_display.utils.path_resolver.get_templates_dir",
                return_value=Path(test_templates_dir),
            ),
            patch(
                "rpi_weather_display.utils.path_resolver.get_static_dir",
                return_value=Path(nonexistent_static_dir),
            ),
            patch("rpi_weather_display.server.main.path_resolver.ensure_dir_exists"),
            # We need to patch normalize_path.exists, not Path.exists directly
            patch("rpi_weather_display.server.main.path_resolver.normalize_path") as mock_normalize,
        ):
            # Mock the normalize_path method to return a path with controllable .exists()
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_normalize.return_value = mock_path
            
            # Create server 
            server = WeatherDisplayServer(Path("test_config.yaml"), app_factory=app_factory)
            
            # Replace the server's logger with our mock
            server.logger = mock_logger
            
            # Reset logger to start with clean slate
            mock_logger.reset_mock()
            
            # Call method directly
            server._setup_static_files()
            
            # Verify warning was logged
            warning_message = f"Static files directory not found at {Path(nonexistent_static_dir)}. Some resources may not load correctly."
            mock_logger.warning.assert_called_with(warning_message)
            
            # Verify mount was NOT called
            mock_app.mount.assert_not_called()
    finally:
        # Cleanup temporary directories
        import shutil
        shutil.rmtree(test_templates_dir, ignore_errors=True)


@pytest.mark.asyncio()
async def test_route_handlers(monkeypatch) -> None:
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

    # Create temporary directories for tests
    import tempfile
    test_static_dir = tempfile.mkdtemp()
    test_templates_dir = tempfile.mkdtemp()
    
    try:
        with (
            patch("rpi_weather_display.models.config.AppConfig.from_yaml", return_value=mock_config),
            patch("rpi_weather_display.utils.logging.setup_logging", return_value=MagicMock()),
            patch(
                "rpi_weather_display.utils.path_resolver.get_templates_dir",
                return_value=Path(test_templates_dir),
            ),
            patch(
                "rpi_weather_display.utils.path_resolver.get_static_dir",
                return_value=Path(test_static_dir),
            ),
            patch("rpi_weather_display.server.main.path_resolver.ensure_dir_exists"),
            patch("fastapi.staticfiles.StaticFiles", return_value=MagicMock()),
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
            await render_handler(mock_request)
            server._handle_render.assert_called_once_with(mock_request)

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
    finally:
        # Cleanup temporary directories
        import shutil
        shutil.rmtree(test_static_dir, ignore_errors=True)
        shutil.rmtree(test_templates_dir, ignore_errors=True)


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

    # Create temporary directories for tests
    import tempfile
    test_static_dir = tempfile.mkdtemp()
    test_templates_dir = tempfile.mkdtemp()
    
    try:
        with (
            patch("rpi_weather_display.models.config.AppConfig.from_yaml", return_value=mock_config),
            patch("rpi_weather_display.utils.logging.setup_logging", return_value=mock_logger),
            patch(
                "rpi_weather_display.utils.path_resolver.get_templates_dir",
                return_value=Path(test_templates_dir),
            ),
            patch(
                "rpi_weather_display.utils.path_resolver.get_static_dir",
                return_value=Path(test_static_dir),
            ),
            patch("rpi_weather_display.server.main.path_resolver.ensure_dir_exists"),
            patch("fastapi.staticfiles.StaticFiles", return_value=MagicMock()),
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
                # Call the method
                response = await server._handle_render(request)

                # Verify the response
                assert response == mock_response

                # Test error handling
                error_msg = "Test error"
                server.api_client.get_weather_data = AsyncMock(side_effect=Exception(error_msg))
                
                # Reset the logger mock
                mock_logger.reset_mock()

                # Import needed for HTTPException
                from fastapi import HTTPException

                with pytest.raises(HTTPException) as excinfo:
                    await server._handle_render(request)

                # Verify error was logged
                mock_logger.error.assert_called_once_with(
                    f"Error rendering weather image [test_location]: {error_msg}"
                )
                
                assert excinfo.value.status_code == 500
                assert error_msg in excinfo.value.detail
    finally:
        # Cleanup temporary directories
        import shutil
        shutil.rmtree(test_static_dir, ignore_errors=True)
        shutil.rmtree(test_templates_dir, ignore_errors=True)


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

    # Create temporary directories for tests
    import tempfile
    test_static_dir = tempfile.mkdtemp()
    test_templates_dir = tempfile.mkdtemp()
    
    try:
        with (
            patch("rpi_weather_display.models.config.AppConfig.from_yaml", return_value=mock_config),
            patch("rpi_weather_display.utils.logging.setup_logging", return_value=MagicMock()),
            patch(
                "rpi_weather_display.utils.path_resolver.get_templates_dir",
                return_value=Path(test_templates_dir),
            ),
            patch(
                "rpi_weather_display.utils.path_resolver.get_static_dir",
                return_value=Path(test_static_dir),
            ),
            patch("rpi_weather_display.server.main.path_resolver.ensure_dir_exists"),
            patch("fastapi.staticfiles.StaticFiles", return_value=MagicMock()),
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

            # Verify the result
            assert result == {"test": "data"}

            # Test error handling
            server.api_client.get_weather_data = AsyncMock(side_effect=Exception("Test error"))

            # Import needed for HTTPException
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as excinfo:
                await server._handle_weather()

            assert excinfo.value.status_code == 500
            assert "Test error" in excinfo.value.detail
    finally:
        # Cleanup temporary directories
        import shutil
        shutil.rmtree(test_static_dir, ignore_errors=True)
        shutil.rmtree(test_templates_dir, ignore_errors=True)


def test_server_run_method() -> None:
    """Test the server run method."""
    # Create a proper mock config with host and port
    mock_config = MagicMock()
    mock_config.logging = LoggingConfig(level="INFO")
    mock_config.server.host = "127.0.0.1"
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

    # Create temporary directories for tests
    import tempfile
    test_static_dir = tempfile.mkdtemp()
    test_templates_dir = tempfile.mkdtemp()
    
    try:
        with (
            patch("rpi_weather_display.models.config.AppConfig.from_yaml", return_value=mock_config),
            patch("rpi_weather_display.utils.logging.setup_logging", return_value=mock_logger),
            patch(
                "rpi_weather_display.utils.path_resolver.get_templates_dir",
                return_value=Path(test_templates_dir),
            ),
            patch(
                "rpi_weather_display.utils.path_resolver.get_static_dir",
                return_value=Path(test_static_dir),
            ),
            patch("rpi_weather_display.server.main.path_resolver.ensure_dir_exists"),
            patch("fastapi.staticfiles.StaticFiles", return_value=MagicMock()),
            patch("uvicorn.run", mock_uvicorn.run),
        ):
            # Create the server
            server = WeatherDisplayServer(Path("test_config.yaml"), app_factory=app_factory)
            
            # Replace the server's logger
            server.logger = mock_logger

            # Test run method with default parameters
            server.run()
            mock_uvicorn.run.assert_called_once_with(mock_app, host="127.0.0.1", port=8888)
            mock_uvicorn.run.reset_mock()

            # Test with explicit host and port parameters
            server.run(host="localhost", port=9999)
            mock_uvicorn.run.assert_called_once_with(mock_app, host="localhost", port=9999)
            mock_uvicorn.run.reset_mock()

            # Test with only host parameter
            server.run(host="localhost")
            mock_uvicorn.run.assert_called_once_with(mock_app, host="localhost", port=8888)
            mock_uvicorn.run.reset_mock()

            # Test with only port parameter
            server.run(port=7777)
            mock_uvicorn.run.assert_called_once_with(mock_app, host="127.0.0.1", port=7777)
    finally:
        # Cleanup temporary directories
        import shutil
        shutil.rmtree(test_static_dir, ignore_errors=True)
        shutil.rmtree(test_templates_dir, ignore_errors=True)