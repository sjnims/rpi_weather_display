import argparse
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.models.system import BatteryState, BatteryStatus
from rpi_weather_display.server.api import WeatherAPIClient
from rpi_weather_display.server.renderer import WeatherRenderer
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


class WeatherDisplayServer:
    """Main server application for the weather display."""

    def __init__(self, config_path: Path):
        """Initialize the server.

        Args:
            config_path: Path to configuration file.
        """
        # Load configuration
        self.config = AppConfig.from_yaml(config_path)

        # Set up logging
        self.logger = setup_logging(self.config.logging, "server")

        # Create FastAPI app
        self.app = FastAPI(title="Weather Display Server")

        # Initialize components
        self.api_client = WeatherAPIClient(self.config.weather)

        # Template directory
        self.template_dir = Path(__file__).parent.parent.parent.parent / "templates"
        if not self.template_dir.exists():
            self.template_dir = Path("/etc/rpi-weather-display/templates")

        # Initialize renderer
        self.renderer = WeatherRenderer(self.config, self.template_dir)

        # Cache directory
        self.cache_dir = Path(self.config.server.cache_dir)
        self.cache_dir.mkdir(exist_ok=True, parents=True)

        # Set up routes
        self._setup_routes()

        self.logger.info("Weather Display Server initialized")

    def _setup_routes(self) -> None:
        """Set up FastAPI routes."""

        @self.app.get("/")
        async def root():
            return {"status": "ok", "service": "Weather Display Server"}

        @self.app.post("/render")
        async def render_weather(request: RenderRequest):
            return await self._handle_render(request)

        @self.app.get("/weather")
        async def get_weather():
            return await self._handle_weather()

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
            self.logger.error(f"Error rendering weather image: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def _handle_weather(self) -> dict:
        """Handle weather data request.

        Returns:
            Weather data as dictionary.
        """
        try:
            # Get weather data
            weather_data = await self.api_client.get_weather_data()

            # Return as dict
            return weather_data.dict()
        except Exception as e:
            self.logger.error(f"Error getting weather data: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def run(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Run the server.

        Args:
            host: Host to bind to.
            port: Port to bind to.
        """
        import uvicorn

        self.logger.info(f"Starting Weather Display Server on {host}:{port}")
        uvicorn.run(self.app, host=host, port=port)


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
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
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
