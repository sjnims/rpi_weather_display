"""Tests for the client main module."""
# ruff: noqa: S101, A002, PLR2004, SLF001
# ^ Ignores "Use of assert detected" in test files
# pyright: reportPrivateUsage=false
# ^ Allows tests to access protected members
# pyright: reportUnknownMemberType=false
# pyright: reportAttributeAccessIssue=false

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from rpi_weather_display.client.main import WeatherDisplayClient, main
from rpi_weather_display.models.config import AppConfig
from rpi_weather_display.models.system import BatteryState, BatteryStatus


@pytest.fixture()
def config_path(tmp_path: Path) -> Path:
    """Create a temporary config file for testing."""
    config_content = """
    weather:
      api_key: test_key
      location:
        lat: 0.0
        lon: 0.0
      update_interval_minutes: 30
    display:
      width: 1872
      height: 1404
      rotate: 0
      partial_refresh: true
      refresh_interval_minutes: 30
    power:
      quiet_hours_start: "23:00"
      quiet_hours_end: "06:00"
      low_battery_threshold: 20
      critical_battery_threshold: 10
      wake_up_interval_minutes: 60
      wifi_timeout_seconds: 30
    server:
      url: http://localhost
      port: 8000
      timeout_seconds: 30
    logging:
      level: DEBUG
      file: null
    debug: true
    """
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)
    return config_file


@pytest.fixture()
def mock_display() -> MagicMock:
    """Create a mock display."""
    display = MagicMock()
    display.initialize = MagicMock()
    display.display_image = MagicMock()
    display.close = MagicMock()
    display.sleep = MagicMock()
    return display


@pytest.fixture()
def mock_power_manager() -> MagicMock:
    """Create a mock power manager."""
    power_manager = MagicMock()
    power_manager.initialize = MagicMock()
    power_manager.get_battery_status = MagicMock(
        return_value=BatteryStatus(
            level=75,
            voltage=3.7,
            current=100.0,
            temperature=25.0,
            state=BatteryState.DISCHARGING,
            time_remaining=1200,  # 20 hours
        )
    )
    power_manager.get_system_metrics = MagicMock(
        return_value={
            "cpu_temp": 45.0,
            "cpu_usage": 10.5,
            "memory_usage": 25.2,
            "disk_usage": 42.0,
        }
    )
    power_manager.schedule_wakeup = MagicMock(return_value=True)
    power_manager.shutdown_system = MagicMock()
    return power_manager


@pytest.fixture()
def mock_scheduler() -> MagicMock:
    """Create a mock scheduler."""
    scheduler = MagicMock()
    scheduler.run = MagicMock()
    return scheduler


@pytest.fixture()
def client(
    config_path: Path,
    mock_display: MagicMock,
    mock_power_manager: MagicMock,
    mock_scheduler: MagicMock,
) -> WeatherDisplayClient:
    """Create a WeatherDisplayClient with mocked components."""
    with (
        patch("rpi_weather_display.client.main.EPaperDisplay", return_value=mock_display),
        patch("rpi_weather_display.client.main.PowerManager", return_value=mock_power_manager),
        patch("rpi_weather_display.client.main.Scheduler", return_value=mock_scheduler),
    ):
        client = WeatherDisplayClient(config_path)
        return client


class TestWeatherDisplayClient:
    """Test suite for the WeatherDisplayClient class."""

    def test_init(self, config_path: Path) -> None:
        """Test client initialization."""
        with (
            patch("rpi_weather_display.client.main.EPaperDisplay") as mock_display_cls,
            patch("rpi_weather_display.client.main.PowerManager") as mock_power_cls,
            patch("rpi_weather_display.client.main.Scheduler") as mock_scheduler_cls,
        ):
            client = WeatherDisplayClient(config_path)

            # Check that configuration is loaded
            assert isinstance(client.config, AppConfig)

            # Check that components are initialized
            mock_power_cls.assert_called_once()
            mock_display_cls.assert_called_once()
            mock_scheduler_cls.assert_called_once()

            # Check that cache directory is created
            assert client.cache_dir.exists()
            assert client.current_image_path.name == "current.png"

    def test_initialize(self, client: WeatherDisplayClient) -> None:
        """Test hardware initialization."""
        client.initialize()

        # Verify components are initialized
        client.power_manager.initialize.assert_called_once()  # type: ignore
        client.display.initialize.assert_called_once()  # type: ignore

    def test_update_weather_success(self, client: WeatherDisplayClient) -> None:
        """Test successful weather update."""
        # Mock successful response from server
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"image data"

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = client.update_weather()

            # Verify result
            assert result is True

            # Verify request was made correctly
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert args[0] == "http://localhost:8000/render"
            assert "battery" in kwargs["json"]
            assert "metrics" in kwargs["json"]

            # Verify image was saved
            assert client.current_image_path.exists()

    def test_update_weather_server_error(self, client: WeatherDisplayClient) -> None:
        """Test weather update with server error."""
        # Mock error response from server
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = client.update_weather()

            # Verify result
            assert result is False

            # Verify request was made
            mock_post.assert_called_once()

    def test_update_weather_request_exception(self, client: WeatherDisplayClient) -> None:
        """Test weather update with request exception."""
        with patch(
            "requests.post", side_effect=requests.RequestException("Connection error")
        ) as mock_post:
            result = client.update_weather()

            # Verify result
            assert result is False

            # Verify request was attempted
            mock_post.assert_called_once()

    def test_update_weather_generic_exception(self, client: WeatherDisplayClient) -> None:
        """Test weather update with generic exception."""
        with patch("requests.post", side_effect=Exception("Unexpected error")) as mock_post:
            result = client.update_weather()

            # Verify result
            assert result is False

            # Verify request was attempted
            mock_post.assert_called_once()

    def test_refresh_display_with_cached_image(
        self, client: WeatherDisplayClient, tmp_path: Path
    ) -> None:
        """Test display refresh with cached image."""
        # Create a mock cached image
        client.current_image_path.parent.mkdir(exist_ok=True)
        with open(client.current_image_path, "wb") as f:
            f.write(b"test image data")

        client.refresh_display()

        # Verify display was refreshed with the image
        client.display.display_image.assert_called_once_with(client.current_image_path)  # type: ignore

    def test_refresh_display_no_cached_image_update_success(
        self, client: WeatherDisplayClient
    ) -> None:
        """Test display refresh with no cached image and successful update."""
        # Mock that the current_image_path.exists() returns False to simulate no cached image
        with (
            patch.object(Path, "exists", return_value=False),
            patch.object(client, "update_weather", return_value=True) as mock_update,
        ):
            client.refresh_display()

            # Verify update was attempted
            mock_update.assert_called_once()

            # Verify display was refreshed
            client.display.display_image.assert_called_once()  # type: ignore

    def test_refresh_display_no_cached_image_update_failure(
        self, client: WeatherDisplayClient
    ) -> None:
        """Test display refresh with no cached image and failed update."""
        # Mock that the current_image_path.exists() returns False to simulate no cached image
        with (
            patch.object(Path, "exists", return_value=False),
            patch.object(client, "update_weather", return_value=False) as mock_update,
        ):
            client.refresh_display()

            # Verify update was attempted
            mock_update.assert_called_once()

            # Verify display was not refreshed
            client.display.display_image.assert_not_called()  # type: ignore

    def test_refresh_display_no_cached_image_update_failure_log(
        self, client: WeatherDisplayClient
    ) -> None:
        """Test that error is logged when no cached image and update fails."""
        # Set up a patched logger to verify the error message
        with (
            patch.object(Path, "exists", return_value=False),
            patch.object(client, "update_weather", return_value=False),
            patch.object(client.logger, "error") as mock_error,
            patch.object(client.logger, "info"),
        ):
            # Execute refresh_display
            client.refresh_display()

            # Assert that the error message was logged
            # This directly checks line 135 in the codebase
            mock_error.assert_any_call("No image available and failed to update")

    def test_refresh_display_exception(self, client: WeatherDisplayClient) -> None:
        """Test display refresh with exception."""
        # Mock exception during display
        client.display.display_image.side_effect = Exception("Display error")  # type: ignore

        # Create a mock cached image
        client.current_image_path.parent.mkdir(exist_ok=True)
        with open(client.current_image_path, "wb") as f:
            f.write(b"test image data")

        # This should not raise an exception
        client.refresh_display()

        # Verify display was attempted
        client.display.display_image.assert_called_once()  # type: ignore

    def test_run(self, client: WeatherDisplayClient) -> None:
        """Test the main run method."""
        # Mock methods
        with (
            patch.object(client, "initialize") as mock_initialize,
            patch.object(client, "update_weather") as mock_update,
            patch.object(client, "refresh_display") as mock_refresh,
        ):
            client.run()

            # Verify initialization
            mock_initialize.assert_called_once()

            # Verify initial update and refresh
            mock_update.assert_called_once()
            mock_refresh.assert_called_once()

            # Verify scheduler was run
            client.scheduler.run.assert_called_once()  # type: ignore

            # Verify callbacks were passed correctly
            args, kwargs = client.scheduler.run.call_args  # type: ignore
            assert "refresh_callback" in kwargs
            assert "update_callback" in kwargs
            assert "battery_callback" in kwargs
            assert "sleep_callback" in kwargs

    def test_run_keyboard_interrupt(self, client: WeatherDisplayClient) -> None:
        """Test run method with keyboard interrupt."""
        # Mock initialization to raise KeyboardInterrupt
        client.initialize = MagicMock(side_effect=KeyboardInterrupt())

        # Mock shutdown
        with patch.object(client, "shutdown") as mock_shutdown:
            client.run()

            # Verify shutdown was called
            mock_shutdown.assert_called_once()

    def test_run_exception(self, client: WeatherDisplayClient) -> None:
        """Test run method with exception."""
        # Mock initialization to raise Exception
        client.initialize = MagicMock(side_effect=Exception("Test error"))

        # Mock shutdown
        with patch.object(client, "shutdown") as mock_shutdown:
            client.run()

            # Verify shutdown was called
            mock_shutdown.assert_called_once()

    def test_handle_sleep_debug_mode(self, client: WeatherDisplayClient) -> None:
        """Test sleep handling in debug mode."""
        # Client is initialized with debug=True
        result = client._handle_sleep(15)

        # In debug mode, should not deep sleep
        assert result is False

        # Verify no shutdown attempted
        client.power_manager.schedule_wakeup.assert_not_called()  # type: ignore
        client.power_manager.shutdown_system.assert_not_called()  # type: ignore
        client.display.sleep.assert_not_called()  # type: ignore

    def test_handle_sleep_short_duration(self, client: WeatherDisplayClient) -> None:
        """Test sleep handling with short duration."""
        # Set debug mode to False
        client.config.debug = False

        # Short sleep duration
        result = client._handle_sleep(5)

        # Short duration should not deep sleep
        assert result is False

        # Verify no shutdown attempted
        client.power_manager.schedule_wakeup.assert_not_called()  # type: ignore
        client.power_manager.shutdown_system.assert_not_called()  # type: ignore
        client.display.sleep.assert_not_called()  # type: ignore

    def test_handle_sleep_long_duration(self, client: WeatherDisplayClient) -> None:
        """Test sleep handling with long duration."""
        # Set debug mode to False
        client.config.debug = False

        # Long sleep duration
        result = client._handle_sleep(30)

        # Should deep sleep
        assert result is True

        # Verify proper shutdown sequence
        client.power_manager.schedule_wakeup.assert_called_once_with(30)  # type: ignore
        client.display.sleep.assert_called_once()  # type: ignore
        client.power_manager.shutdown_system.assert_called_once()  # type: ignore

    def test_handle_sleep_wakeup_failure(self, client: WeatherDisplayClient) -> None:
        """Test sleep handling with wakeup scheduling failure."""
        # Set debug mode to False
        client.config.debug = False

        # Mock wakeup scheduling failure
        client.power_manager.schedule_wakeup.return_value = False  # type: ignore

        # Long sleep duration
        result = client._handle_sleep(30)

        # Should not deep sleep if wakeup fails
        assert result is False

        # Verify wakeup was attempted but shutdown wasn't
        client.power_manager.schedule_wakeup.assert_called_once_with(30)  # type: ignore
        client.display.sleep.assert_not_called()  # type: ignore
        client.power_manager.shutdown_system.assert_not_called()  # type: ignore

    def test_shutdown(self, client: WeatherDisplayClient) -> None:
        """Test client shutdown."""
        client.shutdown()

        # Verify display is closed
        client.display.close.assert_called_once()  # type: ignore

    def test_main_path_for_early_return(self) -> None:
        """Test the early return path in the main function when config file doesn't exist."""
        # Mock a non-existent config file
        mock_args = MagicMock()
        mock_args.config = MagicMock(spec=Path)
        mock_args.config.exists.return_value = False

        # Mock argparse
        mock_parser = MagicMock()
        mock_parser.parse_args.return_value = mock_args

        with (
            patch("argparse.ArgumentParser", return_value=mock_parser),
            patch("builtins.print") as mock_print,
            patch("rpi_weather_display.client.main.WeatherDisplayClient") as mock_client_cls,
        ):
            # Call the main function
            from rpi_weather_display.client.main import main

            result = main()

            # Verify error message was printed and client was not created
            mock_print.assert_called_once()
            mock_client_cls.assert_not_called()

            # Return should be None
            assert result is None


class TestMainFunction:
    """Test suite for the main function."""

    @patch("rpi_weather_display.client.main.WeatherDisplayClient")
    @patch("rpi_weather_display.client.main.argparse.ArgumentParser")
    def test_main_success(self, mock_parser_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        """Test successful execution of main function."""
        # Mock argument parser
        mock_parser = MagicMock()
        mock_parser_cls.return_value = mock_parser

        # Mock parsed args
        mock_args = MagicMock()
        mock_args.config = MagicMock(spec=Path)
        mock_args.config.exists.return_value = True
        mock_parser.parse_args.return_value = mock_args

        # Mock client
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        # Call main function
        main()

        # Verify client was created and run
        mock_client_cls.assert_called_once_with(mock_args.config)
        mock_client.run.assert_called_once()

    @patch("rpi_weather_display.client.main.WeatherDisplayClient")
    @patch("rpi_weather_display.client.main.argparse.ArgumentParser")
    @patch("builtins.print")
    def test_main_config_not_found(
        self, mock_print: MagicMock, mock_parser_cls: MagicMock, mock_client_cls: MagicMock
    ) -> None:
        """Test main function with missing config file."""
        # Mock argument parser
        mock_parser = MagicMock()
        mock_parser_cls.return_value = mock_parser

        # Mock parsed args with non-existent config
        mock_args = MagicMock()
        mock_args.config = MagicMock(spec=Path)
        mock_args.config.exists.return_value = False
        mock_parser.parse_args.return_value = mock_args

        # Call main function
        main()

        # Verify error was printed and client was not created
        mock_print.assert_called_once()
        mock_client_cls.assert_not_called()
