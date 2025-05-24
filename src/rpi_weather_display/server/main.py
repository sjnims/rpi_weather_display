# pyright: reportUnknownMemberType=false

"""Server application for the Raspberry Pi weather display.

Implements a FastAPI web server that processes requests from display clients,
fetches weather data, renders images, and provides preview capabilities.
This is the main server module that initializes and configures the server
application, registers routes, and handles incoming requests.
"""

import argparse
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from rpi_weather_display.constants import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_SERVER_HOST,
    DOWNLOAD_FILENAME,
    IMAGE_FILE_EXTENSION,
    IMAGE_MEDIA_TYPE,
    PREVIEW_BATTERY_CURRENT,
    PREVIEW_BATTERY_LEVEL,
    PREVIEW_BATTERY_TEMP,
    PREVIEW_BATTERY_VOLTAGE,
)
from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.models.system import BatteryState, BatteryStatus
from rpi_weather_display.models.weather import WeatherData
from rpi_weather_display.server.api import WeatherAPIClient
from rpi_weather_display.server.browser_manager import browser_manager
from rpi_weather_display.server.renderer import WeatherRenderer
from rpi_weather_display.utils import path_resolver
from rpi_weather_display.utils.cache_manager import FileCache
from rpi_weather_display.utils.error_utils import get_error_location
from rpi_weather_display.utils.logging import setup_logging
from rpi_weather_display.utils.memory_profiler import MemoryReportDict, memory_profiler
from rpi_weather_display.utils.path_utils import validate_config_path


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifespan - startup and shutdown.

    Args:
        app: FastAPI application instance

    Yields:
        None
    """
    # Startup
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Starting Weather Display Server")

    # Set memory baseline
    memory_profiler.set_baseline()

    yield

    # Shutdown
    logger.info("Shutting down Weather Display Server")

    # Log final memory report
    report = memory_profiler.get_report()
    logger.info(f"Final memory report: {report}")

    await browser_manager.cleanup()


class BatteryInfo(BaseModel):
    """Battery information from client.

    Model representing battery data sent from client devices to the server.
    Used to pass battery status information in render requests.

    Attributes:
        level: Battery charge percentage (0-100)
        state: Battery state (CHARGING, DISCHARGING, etc.)
        voltage: Battery voltage in volts
        current: Battery current in amps
        temperature: Battery temperature in Celsius
    """

    level: int
    state: str
    voltage: float
    current: float
    temperature: float


class RenderRequest(BaseModel):
    """Request model for rendering weather image.

    Contains the data sent by client devices when requesting a weather image.
    Includes battery information and system metrics for context-aware rendering.

    Attributes:
        battery: Battery status information
        metrics: Optional dictionary of system metrics (CPU, memory, etc.)
    """

    battery: BatteryInfo
    metrics: dict[str, float] = {}


class WeatherDisplayServer:
    """Main server application for the weather display.

    Handles initialization of the FastAPI application, routes setup,
    and coordination between API client, renderer, and static file serving.

    This class implements the core server functionality for the weather display
    system, including handling requests from clients, fetching and rendering
    weather data, and providing a browser preview capability.

    Attributes:
        config: Application configuration from YAML
        logger: Configured logger instance
        app: FastAPI application instance
        api_client: Client for OpenWeatherMap API
        template_dir: Directory containing Jinja2 templates
        static_dir: Directory for static assets (CSS, images, etc.)
        renderer: Weather data renderer for HTML and images
        cache_dir: Directory for caching rendered images
    """

    def __init__(
        self,
        config_path: Path,
        app_factory: Callable[[], FastAPI] = lambda: FastAPI(
            title="Weather Display Server", lifespan=lifespan
        ),
    ) -> None:
        """Initialize the server.

        Args:
            config_path: Path to configuration file.
            app_factory: Optional factory function to create FastAPI app.

        Raises:
            FileNotFoundError: If configuration file doesn't exist.
            ValueError: If configuration is invalid.
        """
        # File system operations use path_resolver directly
        # Load configuration
        self.config = AppConfig.from_yaml(config_path)

        # Set up logging
        self.logger = setup_logging(self.config.logging, "server")

        # Create FastAPI app
        self.app = app_factory()

        # Initialize components
        self.api_client = WeatherAPIClient(self.config.weather)

        # Template directory - use path resolver to find templates
        self.template_dir = path_resolver.get_templates_dir()
        self.logger.info(f"Using templates directory: {self.template_dir}")

        # Static directory - use path resolver to find static files
        self.static_dir = path_resolver.get_static_dir()
        self.logger.info(f"Using static directory: {self.static_dir}")

        # Initialize renderer
        self.renderer = WeatherRenderer(self.config, self.template_dir)

        # Cache directory
        if self.config.server.cache_dir:
            self.cache_dir = path_resolver.normalize_path(self.config.server.cache_dir)
            path_resolver.ensure_dir_exists(self.cache_dir)
        else:
            self.cache_dir = path_resolver.cache_dir

        self.logger.info(f"Using cache directory: {self.cache_dir}")

        # Initialize file cache for images
        self.file_cache = FileCache(
            cache_dir=self.cache_dir,
            max_size_mb=50.0,  # 50MB for image cache
            ttl_seconds=3600,  # 1 hour TTL for images
        )

        # Set up routes
        self._setup_routes()

        # Set up static files handling
        self._setup_static_files()

        self.logger.info("Weather Display Server initialized")

    def _setup_routes(self) -> None:
        """Set up FastAPI routes.

        Registers route handlers for the API endpoints:
        - GET /: Server health check
        - POST /render: Generate and return a weather image
        - GET /weather: Return raw weather data
        - GET /preview: Generate HTML preview for browser
        """

        @self.app.get("/")
        async def root() -> dict[str, str]:
            """Root endpoint for health check.

            Returns:
                Dictionary with status information.
            """
            return {"status": "ok", "service": "Weather Display Server"}

        @self.app.post("/render")
        async def render_weather(
            request: RenderRequest, background_tasks: BackgroundTasks
        ) -> Response:
            """Render a weather image for e-paper display.

            Takes battery and system information from the client and generates
            a PNG image of the weather dashboard.

            Args:
                request: Client render request with battery status.
                background_tasks: FastAPI background task queue for cleanup.

            Returns:
                PNG image response.

            Raises:
                HTTPException: If image generation fails.
            """
            return await self._handle_render(request, background_tasks)

        @self.app.get("/weather")
        async def get_weather() -> WeatherData:
            """Get raw weather data.

            Returns the current weather and forecast data. FastAPI automatically
            serializes the Pydantic model to JSON.

            Returns:
                WeatherData model with current conditions and forecasts.

            Raises:
                HTTPException: If weather data cannot be fetched.
            """
            return await self._handle_weather()

        @self.app.get("/memory")
        async def get_memory_status() -> MemoryReportDict:
            """Get memory usage statistics.

            Returns memory profiling information including current usage,
            history, and potential leak detection.

            Returns:
                Dictionary with memory statistics.
            """
            return memory_profiler.get_report()

        @self.app.get("/preview")
        async def preview_weather() -> Response:
            """Preview the weather dashboard in a browser.

            Generates an HTML preview of the weather dashboard for viewing in a browser.
            Uses mock battery values for preview rendering.

            Returns:
                HTML response with the rendered dashboard.

            Raises:
                HTTPException: If preview generation fails.
            """
            try:
                # Get default battery status for preview
                battery_status = BatteryStatus(
                    level=PREVIEW_BATTERY_LEVEL,
                    voltage=PREVIEW_BATTERY_VOLTAGE,
                    current=PREVIEW_BATTERY_CURRENT,
                    temperature=PREVIEW_BATTERY_TEMP,
                    state=BatteryState.FULL,
                )

                # Get weather data
                weather_data = await self.api_client.get_weather_data()

                # Generate HTML
                html = await self.renderer.generate_html(weather_data, battery_status)

                # Return HTML content
                return Response(content=html, media_type="text/html")
            except Exception as e:
                error_location = get_error_location()
                self.logger.error(f"Error generating preview [{error_location}]: {e}")
                raise HTTPException(status_code=500, detail=str(e)) from e

    async def _handle_render(
        self, request: RenderRequest, background_tasks: BackgroundTasks
    ) -> Response:
        """Handle render request.

        Processes a client render request, fetches the latest weather data,
        renders an image, and returns it as a PNG response.

        Args:
            request: Render request data containing battery status and system metrics.
            background_tasks: FastAPI background task queue for cleanup.

        Returns:
            FastAPI response with rendered PNG image.

        Raises:
            HTTPException: If rendering fails for any reason.
        """
        try:
            # Convert battery info to model
            battery_status = BatteryStatus(
                level=request.battery.level,
                voltage=request.battery.voltage,
                current=request.battery.current,
                temperature=request.battery.temperature,
                state=BatteryState(request.battery.state),
            )

            # Get weather data
            weather_data = await self.api_client.get_weather_data()

            # Record memory before rendering
            memory_profiler.record_snapshot()

            # Create a temporary file for the image using path resolver
            tmp_path = path_resolver.get_temp_file(suffix=IMAGE_FILE_EXTENSION)

            # Render the image
            await self.renderer.render_weather_image(weather_data, battery_status, tmp_path)

            # Record memory after rendering
            memory_profiler.record_snapshot()

            # Check for excessive memory growth
            if memory_profiler.check_memory_growth(threshold_mb=100.0):
                self.logger.warning("Excessive memory growth detected during rendering")

            # Return the image with background task to clean up
            def cleanup_temp_file() -> None:
                """Clean up temporary file after response is sent."""
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception as clean_e:
                    self.logger.warning(f"Failed to clean up temp file {tmp_path}: {clean_e}")

            background_tasks.add_task(cleanup_temp_file)

            return FileResponse(tmp_path, media_type=IMAGE_MEDIA_TYPE, filename=DOWNLOAD_FILENAME)
        except Exception as e:
            error_location = get_error_location()
            self.logger.error(f"Error rendering weather image [{error_location}]: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    async def _handle_weather(self) -> WeatherData:
        """Handle weather data request.

        Fetches the latest weather data and returns it as a Pydantic model.
        FastAPI will automatically serialize this to JSON.

        Returns:
            WeatherData model containing current weather and forecasts.

        Raises:
            HTTPException: If weather data cannot be fetched.
        """
        try:
            # Get weather data
            weather_data = await self.api_client.get_weather_data()

            # Return the Pydantic model directly
            # FastAPI will automatically serialize it to JSON with proper datetime handling
            return weather_data
        except Exception as e:
            error_location = get_error_location()
            self.logger.error(f"Error getting weather data [{error_location}]: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    def _setup_static_files(self) -> None:
        """Set up static files handling.

        Configures the FastAPI application to serve static files (CSS, images)
        from the static directory if it exists.
        """
        # Use path resolver to check if static directory exists
        if path_resolver.normalize_path(self.static_dir).exists():
            self.app.mount("/static", StaticFiles(directory=str(self.static_dir)), name="static")
        else:
            self.logger.warning(
                f"Static files directory not found at {self.static_dir}. "
                "Some resources may not load correctly."
            )

    def run(self, host: str | None = None, port: int | None = None) -> None:
        """Run the server.

        Starts the Uvicorn ASGI server with the configured FastAPI application.

        Args:
            host: Host to bind to. Defaults to server config or 127.0.0.1 (localhost).
            port: Port to bind to. Defaults to server config or 8000.
        """
        import uvicorn

        # Use provided values, config values, or defaults
        bind_host = host or getattr(self.config.server, "host", DEFAULT_SERVER_HOST)
        bind_port = port or self.config.server.port

        self.logger.info(f"Starting Weather Display Server on {bind_host}:{bind_port}")

        # Force Uvicorn to use standard logging
        print(f"Starting Uvicorn on http://{bind_host}:{bind_port}")

        uvicorn.run(self.app, host=bind_host, port=bind_port)


def main() -> None:
    """Main entry point for the server.

    Parses command line arguments, initializes the server with the
    specified configuration, and starts it running.
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Weather Display Server")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,  # Will use path_resolver to determine default
        help=f"Path to configuration file (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--host", type=str, help="Host to bind to (default: 127.0.0.1 or config value)"
    )
    parser.add_argument("--port", type=int, help="Port to bind to (default: 8000 or config value)")
    args = parser.parse_args()

    # Validate and resolve the config path
    config_path = validate_config_path(args.config)

    # Create and run server
    server = WeatherDisplayServer(config_path)
    server.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
