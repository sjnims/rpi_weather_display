# pyright: reportUnknownMemberType=false, reportGeneralTypeIssues=false
# pyright: reportMissingImports=false, reportUnknownVariableType=false
# pyright: reportUnknownParameterType=false

"""Server application for the Raspberry Pi weather display.

Implements a FastAPI web server that processes requests from display clients,
fetches weather data, renders images, and provides preview capabilities.
"""

import argparse
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.models.system import BatteryState, BatteryStatus
from rpi_weather_display.server.api import WeatherAPIClient
from rpi_weather_display.server.renderer import WeatherRenderer
from rpi_weather_display.utils.error_utils import get_error_location
from rpi_weather_display.utils.logging import setup_logging


class BatteryInfo(BaseModel):
    """Battery information from client."""

    level: int
    state: str
    voltage: float
    current: float
    temperature: float


class RenderRequest(BaseModel):
    """Request model for rendering weather image."""

    battery: BatteryInfo
    metrics: dict[str, float] = {}


class RealFileSystem:
    """File system implementation using actual file system operations."""

    def exists(self, path: Path) -> bool:
        """Check if a path exists.

        Args:
            path: Path to check.

        Returns:
            True if the path exists, False otherwise.
        """
        return path.exists()

    def is_dir(self, path: Path) -> bool:
        """Check if a path is a directory.

        Args:
            path: Path to check.

        Returns:
            True if the path is a directory, False otherwise.
        """
        return path.is_dir()


class WeatherDisplayServer:
    """Main server application for the weather display."""

    def __init__(
        self,
        config_path: Path,
        file_system: RealFileSystem | None = None,
        app_factory: Callable[[], FastAPI] = lambda: FastAPI(title="Weather Display Server"),
    ) -> None:
        """Initialize the server.

        Args:
            config_path: Path to configuration file.
            file_system: Optional custom file system handler (useful for testing).
            app_factory: Optional factory function to create FastAPI app.
        """
        self.file_system = file_system or RealFileSystem()
        # Load configuration
        self.config = AppConfig.from_yaml(config_path)

        # Set up logging
        self.logger = setup_logging(self.config.logging, "server")

        # Create FastAPI app
        self.app = app_factory()

        # Initialize components
        self.api_client = WeatherAPIClient(self.config.weather)

        # Template directory
        self.template_dir = self._find_directory(
            "templates",
            [
                Path(__file__).parent.parent.parent.parent / "templates",
                Path("/etc/rpi-weather-display/templates"),
            ],
        )

        # Static directory
        self.static_dir = self._find_directory(
            "static",
            [
                Path(__file__).parent.parent.parent.parent / "static",
                Path("/etc/rpi-weather-display/static"),
            ],
        )

        # Initialize renderer
        self.renderer = WeatherRenderer(self.config, self.template_dir)

        # Cache directory
        self.cache_dir = Path(self.config.server.cache_dir)
        self.cache_dir.mkdir(exist_ok=True, parents=True)

        # Set up routes
        self._setup_routes()

        # Set up static files handling
        self._setup_static_files()

        self.logger.info("Weather Display Server initialized")

    def _setup_routes(self) -> None:
        """Set up FastAPI routes."""

        @self.app.get("/")
        async def root() -> dict[str, str]:
            return {"status": "ok", "service": "Weather Display Server"}

        @self.app.post("/render")
        async def render_weather(request: RenderRequest) -> Response:
            return await self._handle_render(request)

        @self.app.get("/weather")
        async def get_weather() -> dict[str, Any]:
            return await self._handle_weather()

        @self.app.get("/preview")
        async def preview_weather() -> Response:
            """Preview the weather dashboard in a browser."""
            try:
                # Get default battery status for preview
                battery_status = BatteryStatus(
                    level=85,
                    voltage=3.9,
                    current=0.5,
                    temperature=25.0,
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

    async def _handle_render(self, request: RenderRequest) -> Response:
        """Handle render request.

        Args:
            request: Render request data.

        Returns:
            FastAPI response with rendered image.
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

            # Create a temporary file for the image
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = Path(tmp.name)

            # Render the image
            await self.renderer.render_weather_image(weather_data, battery_status, tmp_path)

            # Return the image
            return FileResponse(tmp_path, media_type="image/png", filename="weather.png")
        except Exception as e:
            error_location = get_error_location()
            self.logger.error(f"Error rendering weather image [{error_location}]: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    async def _handle_weather(self) -> dict[str, Any]:
        """Handle weather data request.

        Returns:
            Weather data as dictionary.
        """
        try:
            # Get weather data
            weather_data = await self.api_client.get_weather_data()

            # Return as dict
            return weather_data.model_dump()
        except Exception as e:
            error_location = get_error_location()
            self.logger.error(f"Error getting weather data [{error_location}]: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    def _find_directory(self, name: str, candidates: list[Path]) -> Path:
        """Find a directory from a list of candidates.

        Args:
            name: Name of directory for logging.
            candidates: List of paths to check in order.

        Returns:
            The first existing path, or the first candidate if none exist.
        """
        for path in candidates:
            if self.file_system.exists(path):
                return path

        self.logger.warning(
            f"{name.capitalize()} directory not found. Some resources may not load correctly."
        )
        return candidates[0]  # Return first candidate as default

    def _setup_static_files(self) -> None:
        """Set up static files handling."""
        if self.static_dir and self.file_system.exists(self.static_dir):
            self.app.mount("/static", StaticFiles(directory=self.static_dir), name="static")
        else:
            self.logger.warning(
                "Static files directory not found. Some resources may not load correctly."
            )

    def run(self, host: str | None = None, port: int | None = None) -> None:
        """Run the server.

        Args:
            host: Host to bind to. Defaults to server config or 127.0.0.1 (localhost).
            port: Port to bind to. Defaults to server config or 8000.
        """
        import uvicorn

        # Use provided values, config values, or defaults
        bind_host = host or getattr(self.config.server, "host", "127.0.0.1")
        bind_port = port or self.config.server.port

        self.logger.info(f"Starting Weather Display Server on {bind_host}:{bind_port}")
        uvicorn.run(self.app, host=bind_host, port=bind_port)


def main() -> None:
    """Main entry point for the server."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Weather Display Server")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("/etc/rpi-weather-display/config.yaml"),
        help="Path to configuration file",
    )
    parser.add_argument(
        "--host", type=str, help="Host to bind to (default: 127.0.0.1 or config value)"
    )
    parser.add_argument("--port", type=int, help="Port to bind to (default: 8000 or config value)")
    args = parser.parse_args()

    # Check if config file exists
    if not args.config.exists():
        print(f"Error: Configuration file not found at {args.config}")
        return

    # Create and run server
    server = WeatherDisplayServer(args.config)
    server.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
