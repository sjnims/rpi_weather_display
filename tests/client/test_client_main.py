"""Tests for the async weather display client."""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from rpi_weather_display.client.main import AsyncWeatherDisplayClient, main
from rpi_weather_display.models.system import BatteryState, BatteryStatus
from rpi_weather_display.utils.power_manager import PowerState


class TestAsyncWeatherDisplayClient:
    """Test the AsyncWeatherDisplayClient class."""
    
    def _mock_network_manager(self, client: AsyncWeatherDisplayClient, connected: bool = True) -> None:
        """Helper to mock network manager for tests."""
        # Create network manager as a Mock with proper async context manager
        client.network_manager = Mock()
        client.network_manager.update_battery_status = Mock()
        
        # Create a proper async context manager mock
        context_manager = AsyncMock()
        context_manager.__aenter__ = AsyncMock(return_value=connected)
        context_manager.__aexit__ = AsyncMock(return_value=None)
        
        # Use a lambda to return the context manager to avoid async detection issues
        client.network_manager.ensure_connectivity = lambda: context_manager

    @pytest.fixture()
    def mock_config_path(self, tmp_path: Path) -> Path:
        """Create a mock configuration file."""
        config_path = tmp_path / "test_config.yaml"
        config_content = """
weather:
  api_key: "test_key"
  location:
    lat: 40.7128
    lon: -74.0060
  city_name: "New York"
display:
  width: 800
  height: 600
server:
  url: "http://localhost"
  port: 8000
  timeout_seconds: 30
power:
  quiet_hours_start: "22:00"
  quiet_hours_end: "06:00"
logging:
  level: "INFO"
debug: false
"""
        config_path.write_text(config_content)
        return config_path

    @pytest.fixture()
    def async_client(self, mock_config_path: Path) -> AsyncWeatherDisplayClient:
        """Create an AsyncWeatherDisplayClient instance."""
        with patch("rpi_weather_display.client.main.PowerStateManager"), \
             patch("rpi_weather_display.client.main.EPaperDisplay"), \
             patch("rpi_weather_display.client.main.AsyncNetworkManager"), \
             patch("rpi_weather_display.client.main.setup_logging") as mock_logging:
            # Mock the logger to prevent stdout pollution
            mock_logger = Mock()
            mock_logger.info = Mock()
            mock_logger.error = Mock()
            mock_logger.warning = Mock()
            mock_logger.debug = Mock()
            mock_logging.return_value = mock_logger
            
            client = AsyncWeatherDisplayClient(mock_config_path)
            # Mock the http client
            client._http_client = AsyncMock(spec=httpx.AsyncClient)
            return client

    def test_init(self, mock_config_path: Path) -> None:
        """Test client initialization."""
        with patch("rpi_weather_display.client.main.PowerStateManager") as mock_power, \
             patch("rpi_weather_display.client.main.EPaperDisplay") as mock_display, \
             patch("rpi_weather_display.client.main.AsyncNetworkManager") as mock_network:
            
            client = AsyncWeatherDisplayClient(mock_config_path)
            
            assert client.config is not None
            assert client.logger is not None
            assert client._running is False
            assert client._http_client is None
            assert client._semaphore._value == 2  # Max concurrent operations
            
            mock_power.assert_called_once()
            mock_display.assert_called_once()
            mock_network.assert_called_once()

    def test_initialize(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test hardware initialization."""
        async_client.power_manager = Mock()
        async_client.display = Mock()
        
        async_client.initialize()
        
        async_client.power_manager.initialize.assert_called_once()
        async_client.power_manager.register_state_change_callback.assert_called_once()
        async_client.display.initialize.assert_called_once()

    @pytest.mark.asyncio()
    async def test_get_http_client(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test HTTP client creation and reuse."""
        # First call should create a new client
        async_client._http_client = None
        client1 = await async_client._get_http_client()
        assert isinstance(client1, httpx.AsyncClient)
        
        # Second call should return the same client
        client2 = await async_client._get_http_client()
        assert client1 is client2

    @pytest.mark.asyncio()
    async def test_update_weather_success(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test successful weather update."""
        # Mock dependencies
        async_client.power_manager = Mock()
        async_client.power_manager.get_battery_status.return_value = BatteryStatus(
            level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0
        )
        async_client.power_manager.get_system_metrics.return_value = {
            "cpu_percent": 10.0,
            "memory_percent": 30.0
        }
        
        # Mock network manager
        self._mock_network_manager(async_client, connected=True)
        
        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.content = b"image_data"
        
        async_client._http_client = AsyncMock()
        async_client._http_client.post = AsyncMock(return_value=mock_response)
        
        # Mock file write
        with patch("rpi_weather_display.client.main.write_bytes") as mock_write:
            result = await async_client.update_weather()
            
            assert result is True
            async_client.network_manager.update_battery_status.assert_called_once()  # type: ignore[attr-defined]
            async_client._http_client.post.assert_called_once()
            mock_write.assert_called_once()
            async_client.power_manager.record_weather_update.assert_called_once()

    @pytest.mark.asyncio()
    async def test_update_weather_no_network(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test weather update when network connection fails."""
        # Mock dependencies
        async_client.power_manager = Mock()
        async_client.power_manager.get_battery_status.return_value = BatteryStatus(
            level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0
        )
        
        # Mock network manager to return no connection
        self._mock_network_manager(async_client, connected=False)
        
        result = await async_client.update_weather()
        
        assert result is False
        async_client.network_manager.update_battery_status.assert_called_once()  # type: ignore[attr-defined]
        # HTTP client should not be called if no network
        if async_client._http_client and hasattr(async_client._http_client, 'post'):
            async_client._http_client.post.assert_not_called()  # type: ignore[attr-defined]

    @pytest.mark.asyncio()
    async def test_update_weather_server_error(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test weather update with server error."""
        # Mock dependencies
        async_client.power_manager = Mock()
        async_client.power_manager.get_battery_status.return_value = BatteryStatus(
            level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0
        )
        async_client.power_manager.get_system_metrics.return_value = {}
        
        # Mock network manager
        self._mock_network_manager(async_client, connected=True)
        
        # Mock HTTP error response
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        
        async_client._http_client = AsyncMock()
        async_client._http_client.post = AsyncMock(return_value=mock_response)
        
        result = await async_client.update_weather()
        
        assert result is False
        async_client.power_manager.record_weather_update.assert_not_called()

    @pytest.mark.asyncio()
    async def test_update_weather_network_error(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test weather update with network error."""
        # Mock dependencies
        async_client.power_manager = Mock()
        async_client.power_manager.get_battery_status.return_value = BatteryStatus(
            level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0
        )
        async_client.power_manager.get_system_metrics.return_value = {}
        
        # Mock network manager
        self._mock_network_manager(async_client, connected=True)
        
        # Mock network error
        async_client._http_client = AsyncMock()
        async_client._http_client.post = AsyncMock(
            side_effect=httpx.NetworkError("Connection failed")
        )
        
        result = await async_client.update_weather()
        
        assert result is False

    @pytest.mark.asyncio()
    async def test_update_weather_timeout(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test weather update with timeout."""
        # Mock dependencies
        async_client.power_manager = Mock()
        async_client.power_manager.get_battery_status.return_value = BatteryStatus(
            level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0
        )
        async_client.power_manager.get_system_metrics.return_value = {}
        
        # Mock network manager
        self._mock_network_manager(async_client, connected=True)
        
        # Mock timeout error
        async_client._http_client = AsyncMock()
        async_client._http_client.post = AsyncMock(
            side_effect=httpx.TimeoutException("Request timed out")
        )
        
        result = await async_client.update_weather()
        
        assert result is False

    @pytest.mark.asyncio()
    async def test_update_weather_http_error(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test weather update with HTTP error."""
        # Mock dependencies
        async_client.power_manager = Mock()
        async_client.power_manager.get_battery_status.return_value = BatteryStatus(
            level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0
        )
        async_client.power_manager.get_system_metrics.return_value = {}
        
        # Mock network manager
        self._mock_network_manager(async_client, connected=True)
        
        # Mock HTTP error
        async_client._http_client = AsyncMock()
        async_client._http_client.post = AsyncMock(
            side_effect=httpx.HTTPError("HTTP error occurred")
        )
        
        result = await async_client.update_weather()
        
        assert result is False

    @pytest.mark.asyncio()
    async def test_update_weather_general_exception(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test weather update with general exception."""
        # Mock dependencies
        async_client.power_manager = Mock()
        async_client.power_manager.get_battery_status.return_value = BatteryStatus(
            level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0
        )
        async_client.power_manager.get_system_metrics.return_value = {}
        
        # Mock network manager
        self._mock_network_manager(async_client, connected=True)
        
        # Mock general exception
        async_client._http_client = AsyncMock()
        async_client._http_client.post = AsyncMock(
            side_effect=Exception("Unexpected error")
        )
        
        result = await async_client.update_weather()
        
        assert result is False

    def test_refresh_display_with_cached_image(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test display refresh with cached image."""
        # Mock dependencies
        async_client.power_manager = Mock()
        async_client.power_manager.get_battery_status.return_value = BatteryStatus(
            level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0
        )
        async_client.display = Mock()
        
        # Mock cached image exists
        with patch("rpi_weather_display.client.main.file_exists", return_value=True):
            async_client.refresh_display()
            
            async_client.display.update_battery_status.assert_called_once()
            async_client.display.display_image.assert_called_once()
            async_client.power_manager.record_display_refresh.assert_called_once()

    def test_refresh_display_no_cached_image_update_success(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test display refresh without cached image - update succeeds."""
        # Mock dependencies
        async_client.power_manager = Mock()
        async_client.power_manager.get_battery_status.return_value = BatteryStatus(
            level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0
        )
        async_client.display = Mock()
        
        # Mock the update_weather to return True
        async_client.update_weather = AsyncMock(return_value=True)
        
        # Mock no cached image exists
        with patch("rpi_weather_display.client.main.file_exists", return_value=False), \
             patch("rpi_weather_display.client.main.asyncio.new_event_loop") as mock_loop_fn, \
             patch("rpi_weather_display.client.main.asyncio.set_event_loop"):
            
            # Mock event loop to actually run the coroutine
            mock_loop = Mock()
            mock_loop_fn.return_value = mock_loop
            
            # Make run_until_complete actually execute the coroutine
            async def run_coro(coro: Any) -> Any:
                return await coro
            
            mock_loop.run_until_complete.side_effect = lambda coro: asyncio.run(run_coro(coro))
            
            async_client.refresh_display()
            
            # Verify update was attempted
            mock_loop.run_until_complete.assert_called_once()
            mock_loop.close.assert_called_once()
            
            # Verify display was updated
            async_client.display.update_battery_status.assert_called_once()
            async_client.display.display_image.assert_called_once()
            async_client.power_manager.record_display_refresh.assert_called_once()

    def test_refresh_display_no_cached_image_update_fails(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test display refresh without cached image - update fails."""
        # Mock dependencies
        async_client.power_manager = Mock()
        async_client.power_manager.get_battery_status.return_value = BatteryStatus(
            level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0
        )
        async_client.display = Mock()
        
        # Mock the update_weather to return False
        async_client.update_weather = AsyncMock(return_value=False)
        
        # Mock no cached image exists
        with patch("rpi_weather_display.client.main.file_exists", return_value=False), \
             patch("rpi_weather_display.client.main.asyncio.new_event_loop") as mock_loop_fn, \
             patch("rpi_weather_display.client.main.asyncio.set_event_loop"):
            
            # Mock event loop to actually run the coroutine
            mock_loop = Mock()
            mock_loop_fn.return_value = mock_loop
            
            # Make run_until_complete actually execute the coroutine
            async def run_coro(coro: Any) -> Any:
                return await coro
            
            mock_loop.run_until_complete.side_effect = lambda coro: asyncio.run(run_coro(coro))
            
            async_client.refresh_display()
            
            # Verify update was attempted
            mock_loop.run_until_complete.assert_called_once()
            mock_loop.close.assert_called_once()
            
            # Verify display was NOT updated
            async_client.display.display_image.assert_not_called()
            async_client.power_manager.record_display_refresh.assert_not_called()

    def test_refresh_display_exception(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test display refresh with exception."""
        # Mock dependencies
        async_client.power_manager = Mock()
        async_client.power_manager.get_battery_status.return_value = BatteryStatus(
            level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0
        )
        async_client.display = Mock()
        async_client.display.display_image.side_effect = Exception("Display error")
        
        # Mock cached image exists
        with patch("rpi_weather_display.client.main.file_exists", return_value=True):
            # Should not raise exception
            async_client.refresh_display()
            
            # Verify exception was caught
            async_client.display.display_image.assert_called_once()

    def test_handle_power_state_change_critical(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test handling critical power state change."""
        # Mock dependencies
        async_client.display = Mock()
        async_client.power_manager = Mock()
        async_client._running = True
        
        # Mock the shutdown method to prevent async issues
        async_client.shutdown = AsyncMock()
        
        # Mock asyncio event loop creation
        with patch("rpi_weather_display.client.main.asyncio.new_event_loop") as mock_loop_fn, \
             patch("rpi_weather_display.client.main.asyncio.set_event_loop"):
            
            mock_loop = Mock()
            mock_loop_fn.return_value = mock_loop
            
            # Make run_until_complete actually execute the coroutine
            async def run_coro(coro: Any) -> Any:
                return await coro
            
            mock_loop.run_until_complete.side_effect = lambda coro: asyncio.run(run_coro(coro))
            
            # Trigger critical state change
            async_client._handle_power_state_change(PowerState.NORMAL, PowerState.CRITICAL)
            
            # Verify critical shutdown sequence
            async_client.display.display_text.assert_called_once_with(
                "CRITICAL BATTERY", "Shutting down to preserve battery"
            )
            assert async_client._running is False
            async_client.power_manager.schedule_wakeup.assert_called_once()
            async_client.power_manager.shutdown_system.assert_called_once()

    def test_handle_power_state_change_critical_with_exception(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test handling critical power state change with exceptions."""
        # Mock dependencies
        async_client.display = Mock()
        async_client.display.display_text.side_effect = Exception("Display error")
        async_client.power_manager = Mock()
        async_client.power_manager.schedule_wakeup = Mock(return_value=True)
        # Make shutdown fail in exception handler to trigger RuntimeError
        async_client.power_manager.shutdown_system.side_effect = Exception("Final error")
        async_client._running = True
        
        # Use patch to mock the event loop - make shutdown() fail to trigger exception handler
        with patch("asyncio.new_event_loop") as mock_new_loop:
            mock_loop = Mock()
            mock_new_loop.return_value = mock_loop
            # Make run_until_complete raise an exception to trigger the exception handler
            mock_loop.run_until_complete = Mock(side_effect=Exception("Shutdown failed"))
        
            # Trigger critical state change - should raise due to shutdown failure in exception handler
            with pytest.raises(RuntimeError, match="Failed to perform critical shutdown"):
                async_client._handle_power_state_change(PowerState.NORMAL, PowerState.CRITICAL)
        
        # Verify shutdown was attempted in exception handler
        assert async_client.power_manager.shutdown_system.call_count == 1

    def test_handle_power_state_change_non_critical(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test handling non-critical power state changes."""
        # Mock dependencies
        async_client.display = Mock()
        async_client.power_manager = Mock()
        async_client._running = True
        
        # Trigger non-critical state change
        async_client._handle_power_state_change(PowerState.CONSERVING, PowerState.NORMAL)
        
        # Verify no shutdown sequence
        async_client.display.display_text.assert_not_called()
        assert async_client._running is True
        async_client.power_manager.shutdown_system.assert_not_called()

    def test_handle_sleep_deep_sleep_scenario(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test deep sleep handling."""
        async_client.config.debug = False
        async_client.power_manager = Mock()
        async_client.power_manager.schedule_wakeup.return_value = True
        async_client.display = Mock()
        
        # Test with long sleep duration (should trigger deep sleep)
        result = async_client._handle_sleep(30)  # 30 minutes
        
        assert result is True
        async_client.power_manager.schedule_wakeup.assert_called_once_with(30, dynamic=True)
        async_client.display.sleep.assert_called_once()
        async_client.power_manager.shutdown_system.assert_called_once()

    def test_handle_sleep_debug_mode(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test sleep handling in debug mode."""
        async_client.config.debug = True
        async_client.power_manager = Mock()
        
        # Should not trigger deep sleep in debug mode
        result = async_client._handle_sleep(30)
        
        assert result is False
        async_client.power_manager.schedule_wakeup.assert_not_called()

    def test_handle_sleep_short_duration(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test sleep handling with short duration."""
        async_client.config.debug = False
        async_client.power_manager = Mock()
        
        # Test with short sleep duration (should not trigger deep sleep)
        result = async_client._handle_sleep(5)  # 5 minutes
        
        assert result is False
        async_client.power_manager.schedule_wakeup.assert_not_called()

    def test_handle_sleep_schedule_wakeup_fails(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test sleep handling when schedule_wakeup fails."""
        async_client.config.debug = False
        async_client.power_manager = Mock()
        async_client.power_manager.schedule_wakeup.return_value = False
        async_client.display = Mock()
        
        # Test with long sleep duration but wakeup scheduling fails
        result = async_client._handle_sleep(30)  # 30 minutes
        
        assert result is False
        async_client.power_manager.schedule_wakeup.assert_called_once_with(30, dynamic=True)
        async_client.display.sleep.assert_not_called()
        async_client.power_manager.shutdown_system.assert_not_called()

    @pytest.mark.asyncio()
    async def test_shutdown(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test client shutdown."""
        # Mock dependencies
        async_client._http_client = AsyncMock(spec=httpx.AsyncClient)
        async_client._http_client.aclose = AsyncMock()
        async_client.display = Mock()
        
        # Keep a reference to the mocked client before shutdown
        http_client_mock = async_client._http_client
        
        await async_client.shutdown()
        
        http_client_mock.aclose.assert_called_once()
        async_client.display.close.assert_called_once()
        assert async_client._http_client is None

    @pytest.mark.asyncio()
    async def test_shutdown_no_http_client(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test client shutdown when no HTTP client exists."""
        # No HTTP client
        async_client._http_client = None
        async_client.display = Mock()
        
        await async_client.shutdown()
        
        # Should not crash
        async_client.display.close.assert_called_once()

    @pytest.mark.asyncio()
    async def test_shutdown_no_display(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test client shutdown when no display exists."""
        # Mock HTTP client
        mock_http_client = AsyncMock(spec=httpx.AsyncClient)
        mock_http_client.aclose = AsyncMock()
        async_client._http_client = mock_http_client
        # Remove display to test edge case
        async_client.display = None  # type: ignore[assignment]
        
        await async_client.shutdown()
        
        # Should not crash and http client should be closed
        mock_http_client.aclose.assert_called_once()
        # Verify http client is set to None after shutdown
        assert async_client._http_client is None

    @pytest.mark.asyncio()
    async def test_run_main_loop(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test the main run loop."""
        # Mock dependencies
        async_client.power_manager = Mock()
        async_client.power_manager.get_current_state.return_value = PowerState.NORMAL
        async_client.power_manager.get_battery_status.return_value = BatteryStatus(
            level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0
        )
        async_client.power_manager.should_update_weather.return_value = False
        async_client.power_manager.should_refresh_display.return_value = False
        async_client.power_manager.calculate_sleep_time.return_value = 1  # 1 second
        
        async_client.display = Mock()
        
        # Mock methods
        async_client.initialize = Mock()
        async_client.update_weather = AsyncMock(return_value=True)
        async_client.refresh_display = Mock()
        async_client.shutdown = AsyncMock()
        
        # Run for a short time then stop
        async def stop_after_delay() -> None:
            await asyncio.sleep(0.1)
            async_client._running = False
        
        # Run both coroutines concurrently
        await asyncio.gather(
            async_client.run(),
            stop_after_delay()
        )
        
        # Verify initialization and updates were called
        async_client.initialize.assert_called_once()
        async_client.update_weather.assert_called()
        async_client.refresh_display.assert_called()

    @pytest.mark.asyncio()
    async def test_run_quiet_hours_transitions(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test quiet hours transitions in main loop."""
        # Mock dependencies
        async_client.power_manager = Mock()
        async_client.power_manager.get_battery_status.return_value = BatteryStatus(
            level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0
        )
        async_client.power_manager.should_update_weather.return_value = False
        async_client.power_manager.should_refresh_display.return_value = False
        async_client.power_manager.calculate_sleep_time.return_value = 0.1
        
        async_client.display = Mock()
        
        # Mock methods
        async_client.initialize = Mock()
        async_client.update_weather = AsyncMock(return_value=True)
        async_client.refresh_display = Mock()
        async_client.shutdown = AsyncMock()
        
        # Simulate state transitions
        state_sequence = [
            PowerState.QUIET_HOURS,  # First check - should sleep display
            PowerState.QUIET_HOURS,  # Second check - no change
            PowerState.NORMAL,       # Third check - should wake display
        ]
        async_client.power_manager.get_current_state.side_effect = state_sequence
        
        # Track iterations
        iteration_count = 0
        
        async def stop_after_iterations() -> None:
            nonlocal iteration_count
            while iteration_count < 4:  # Need 4 iterations to ensure transition happens
                await asyncio.sleep(0.05)
            async_client._running = False
        
        # Override sleep to count iterations
        original_sleep = asyncio.sleep
        async def mock_sleep(duration: float) -> None:
            nonlocal iteration_count
            iteration_count += 1
            await original_sleep(min(duration, 0.01))
        
        with patch("asyncio.sleep", mock_sleep):
            # Run both coroutines concurrently
            await asyncio.gather(
                async_client.run(),
                stop_after_iterations()
            )
        
        # Verify display sleep/wake transitions
        assert async_client.display.sleep.call_count >= 1
        assert async_client.refresh_display.call_count >= 2  # Initial + wake from quiet hours

    @pytest.mark.asyncio()
    async def test_run_with_charging_during_quiet_hours(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test charging behavior during quiet hours."""
        # Mock dependencies
        async_client.power_manager = Mock()
        async_client.power_manager.get_current_state.return_value = PowerState.QUIET_HOURS
        async_client.power_manager.get_battery_status.side_effect = [
            BatteryStatus(level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0),
            BatteryStatus(level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0),
            BatteryStatus(level=85, state=BatteryState.CHARGING, voltage=4.0, current=0.5, temperature=25.0),  # Now charging
        ]
        async_client.power_manager.should_update_weather.return_value = False
        async_client.power_manager.should_refresh_display.return_value = False
        async_client.power_manager.calculate_sleep_time.return_value = 0.1
        
        async_client.display = Mock()
        
        # Mock methods
        async_client.initialize = Mock()
        async_client.update_weather = AsyncMock(return_value=True)
        async_client.refresh_display = Mock()
        async_client.shutdown = AsyncMock()
        
        # Track iterations
        iteration_count = 0
        
        async def stop_after_iterations() -> None:
            nonlocal iteration_count
            while iteration_count < 4:  # Need 4 iterations to ensure charging state is processed
                await asyncio.sleep(0.05)
            async_client._running = False
        
        # Override sleep to count iterations
        original_sleep = asyncio.sleep
        async def mock_sleep(duration: float) -> None:
            nonlocal iteration_count
            iteration_count += 1
            await original_sleep(min(duration, 0.01))
        
        with patch("asyncio.sleep", mock_sleep):
            # Run both coroutines concurrently
            await asyncio.gather(
                async_client.run(),
                stop_after_iterations()
            )
        
        # Verify display woke up when charging started
        assert async_client.refresh_display.call_count >= 2  # Initial + wake when charging

    @pytest.mark.asyncio()
    async def test_run_with_update_triggers(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test weather update and display refresh triggers in main loop."""
        # Mock dependencies
        async_client.power_manager = Mock()
        async_client.power_manager.get_current_state.return_value = PowerState.NORMAL
        async_client.power_manager.get_battery_status.return_value = BatteryStatus(
            level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0
        )
        async_client.power_manager.should_update_weather.side_effect = [False, True, False]  # Trigger on second iteration
        async_client.power_manager.should_refresh_display.side_effect = [False, False, True]  # Trigger on third iteration
        async_client.power_manager.calculate_sleep_time.return_value = 0.1
        
        async_client.display = Mock()
        
        # Mock methods
        async_client.initialize = Mock()
        async_client.update_weather = AsyncMock(return_value=True)
        async_client.refresh_display = Mock()
        async_client.shutdown = AsyncMock()
        
        # Track iterations
        iteration_count = 0
        
        async def stop_after_iterations() -> None:
            nonlocal iteration_count
            while iteration_count < 4:  # Need 4 iterations: initial + 3 loop iterations
                await asyncio.sleep(0.05)
            async_client._running = False
        
        # Override sleep to count iterations
        original_sleep = asyncio.sleep
        async def mock_sleep(duration: float) -> None:
            nonlocal iteration_count
            iteration_count += 1
            await original_sleep(min(duration, 0.01))
        
        with patch("asyncio.sleep", mock_sleep):
            # Run both coroutines concurrently
            await asyncio.gather(
                async_client.run(),
                stop_after_iterations()
            )
        
        # Verify update triggers
        assert async_client.update_weather.call_count == 2  # Initial + triggered
        assert async_client.refresh_display.call_count == 2  # Initial + triggered

    @pytest.mark.asyncio()
    async def test_run_with_deep_sleep_trigger(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test deep sleep trigger in main loop."""
        # Mock dependencies
        async_client.power_manager = Mock()
        async_client.power_manager.get_current_state.return_value = PowerState.NORMAL
        async_client.power_manager.get_battery_status.return_value = BatteryStatus(
            level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0
        )
        async_client.power_manager.should_update_weather.return_value = False
        async_client.power_manager.should_refresh_display.return_value = False
        async_client.power_manager.calculate_sleep_time.return_value = 900  # 15 minutes - should trigger deep sleep
        
        async_client.display = Mock()
        
        # Mock methods
        async_client.initialize = Mock()
        async_client.update_weather = AsyncMock(return_value=True)
        async_client.refresh_display = Mock()
        async_client._handle_sleep = Mock(return_value=True)  # Simulate deep sleep triggered
        async_client.shutdown = AsyncMock()
        
        # Run the loop
        await async_client.run()
        
        # Verify deep sleep was triggered
        async_client._handle_sleep.assert_called_once_with(15)

    @pytest.mark.asyncio()
    async def test_run_with_keyboard_interrupt(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test handling keyboard interrupt in main loop."""
        # Mock dependencies
        async_client.power_manager = Mock()
        async_client.power_manager.get_current_state.return_value = PowerState.NORMAL
        async_client.power_manager.get_battery_status.return_value = BatteryStatus(
            level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0
        )
        async_client.power_manager.should_update_weather.return_value = False
        async_client.power_manager.should_refresh_display.return_value = False
        async_client.power_manager.calculate_sleep_time.return_value = 1
        
        async_client.display = Mock()
        
        # Mock methods
        async_client.initialize = Mock()
        async_client.update_weather = AsyncMock(return_value=True)
        async_client.refresh_display = Mock()
        async_client.shutdown = AsyncMock()
        
        # Simulate keyboard interrupt
        async def trigger_interrupt() -> None:
            await asyncio.sleep(0.1)
            # Set side_effect on the Mock object itself
            async_client.power_manager.calculate_sleep_time = Mock(side_effect=KeyboardInterrupt())
        
        # Run both coroutines
        await asyncio.gather(
            async_client.run(),
            trigger_interrupt()
        )
        
        # Verify clean shutdown
        assert async_client._running is False
        async_client.shutdown.assert_called_once()

    @pytest.mark.asyncio()
    async def test_run_with_general_exception(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test handling general exception in main loop."""
        # Mock dependencies
        async_client.power_manager = Mock()
        async_client.power_manager.get_current_state.return_value = PowerState.NORMAL
        async_client.power_manager.get_battery_status.return_value = BatteryStatus(
            level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0
        )
        async_client.power_manager.should_update_weather.return_value = False
        async_client.power_manager.should_refresh_display.return_value = False
        async_client.power_manager.calculate_sleep_time = Mock(side_effect=Exception("Unexpected error"))
        
        async_client.display = Mock()
        
        # Mock methods
        async_client.initialize = Mock()
        async_client.update_weather = AsyncMock(return_value=True)
        async_client.refresh_display = Mock()
        async_client.shutdown = AsyncMock()
        
        # Run the loop
        await async_client.run()
        
        # Verify clean shutdown
        assert async_client._running is False
        async_client.shutdown.assert_called_once()

    @pytest.mark.asyncio()
    async def test_semaphore_concurrency_limit(self, async_client: AsyncWeatherDisplayClient) -> None:
        """Test that semaphore limits concurrent operations."""
        # Mock dependencies
        async_client.power_manager = Mock()
        async_client.power_manager.get_battery_status.return_value = BatteryStatus(
            level=80, state=BatteryState.DISCHARGING, voltage=3.7, current=-0.5, temperature=25.0
        )
        async_client.power_manager.get_system_metrics.return_value = {}
        async_client.power_manager.record_weather_update = Mock()
        
        # Track concurrent operations inside the semaphore
        concurrent_count = 0
        max_concurrent = 0
        
        # Mock slow HTTP response that tracks concurrency
        async def slow_post(*_args: object, **_kwargs: object) -> AsyncMock:
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            try:
                await asyncio.sleep(0.1)
                response = AsyncMock()
                response.status_code = 200
                response.content = b"image_data"
                return response
            finally:
                concurrent_count -= 1
        
        # Create a real mock client and assign the slow_post method
        mock_http_client = AsyncMock()
        mock_http_client.post = slow_post
        async_client._http_client = mock_http_client
        
        # Try to run more than semaphore limit
        with patch("rpi_weather_display.client.main.write_bytes"):
            results = await asyncio.gather(
                async_client.update_weather(),
                async_client.update_weather(),
                async_client.update_weather(),
                async_client.update_weather(),
            )
        
        # All should succeed
        assert all(results)
        # But max concurrent should be limited by semaphore (2)
        assert max_concurrent <= 2


class TestAsyncMainFunction:
    """Test the main entry point function."""
    
    def _mock_network_manager(self, client: AsyncWeatherDisplayClient, connected: bool = True) -> None:
        """Helper to mock network manager for tests."""
        # Create network manager as a Mock with proper async context manager
        client.network_manager = Mock()
        client.network_manager.update_battery_status = Mock()
        
        # Create a proper async context manager mock
        context_manager = AsyncMock()
        context_manager.__aenter__ = AsyncMock(return_value=connected)
        context_manager.__aexit__ = AsyncMock(return_value=None)
        
        # Use a lambda to return the context manager to avoid async detection issues
        client.network_manager.ensure_connectivity = lambda: context_manager
    
    def test_main_success(self, tmp_path: Path) -> None:
        """Test successful main execution."""
        # Create test config
        config_path = tmp_path / "test_config.yaml"
        config_path.write_text("""
weather:
  api_key: "test"
  location: {lat: 0, lon: 0}
display:
  width: 800
  height: 600
server:
  url: "http://localhost"
  port: 8000
power:
  quiet_hours_start: "22:00"
  quiet_hours_end: "06:00"
logging:
  level: "INFO"
""")
        
        # Mock the client and asyncio.run
        with patch("rpi_weather_display.client.main.AsyncWeatherDisplayClient") as mock_client, \
             patch("rpi_weather_display.client.main.asyncio.run") as mock_run, \
             patch("sys.argv", ["async-client", "--config", str(config_path)]):
            
            mock_client_instance = mock_client.return_value
            # Use a regular Mock since asyncio.run is mocked and won't actually await it
            mock_client_instance.run = Mock()
            
            main()
            
            mock_client.assert_called_once()
            mock_run.assert_called_once()

    def test_main_config_not_found(self) -> None:
        """Test main with missing config file."""
        with patch("sys.argv", ["async-client", "--config", "/nonexistent/config.yaml"]), \
             pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1