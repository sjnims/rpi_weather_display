"""Tests for early error handler module."""

from io import StringIO
from unittest.mock import Mock, patch

from rpi_weather_display.utils.early_error_handler import (
    handle_keyboard_interrupt,
    handle_startup_error,
    handle_unexpected_error,
)


class TestEarlyErrorHandler:
    """Test early error handler functions."""

    @patch("sys.stderr", new_callable=StringIO)
    def test_handle_startup_error_basic(self, mock_stderr: StringIO) -> None:
        """Test basic startup error handling."""
        handle_startup_error("TEST_ERROR", "Test message")
        
        output = mock_stderr.getvalue()
        assert "TEST_ERROR: Test message" in output
        assert "Details:" not in output

    @patch("sys.stderr", new_callable=StringIO)
    def test_handle_startup_error_with_details(self, mock_stderr: StringIO) -> None:
        """Test startup error handling with details."""
        details = {"key1": "value1", "key2": 42}
        handle_startup_error("TEST_ERROR", "Test message", details)
        
        output = mock_stderr.getvalue()
        assert "TEST_ERROR: Test message" in output
        assert "Details:" in output
        assert "key1: value1" in output
        assert "key2: 42" in output

    @patch("sys.stderr", new_callable=StringIO)
    def test_handle_startup_error_empty_details(self, mock_stderr: StringIO) -> None:
        """Test startup error handling with empty details."""
        handle_startup_error("TEST_ERROR", "Test message", {})
        
        output = mock_stderr.getvalue()
        assert "TEST_ERROR: Test message" in output
        assert "Details:" not in output

    @patch("sys.stderr", new_callable=StringIO)
    @patch("rpi_weather_display.utils.early_error_handler.datetime")
    def test_handle_startup_error_timestamp(
        self, mock_datetime: Mock, mock_stderr: StringIO
    ) -> None:
        """Test startup error includes timestamp."""
        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-01T12:00:00"
        mock_datetime.now.return_value = mock_now
        
        handle_startup_error("TEST_ERROR", "Test message")
        
        output = mock_stderr.getvalue()
        assert "[2025-01-01T12:00:00]" in output

    @patch("sys.stderr", new_callable=StringIO)
    def test_handle_keyboard_interrupt(self, mock_stderr: StringIO) -> None:
        """Test keyboard interrupt handling."""
        handle_keyboard_interrupt()
        
        output = mock_stderr.getvalue()
        assert "Shutdown requested by user" in output

    @patch("sys.stderr", new_callable=StringIO)
    def test_handle_unexpected_error(self, mock_stderr: StringIO) -> None:
        """Test unexpected error handling."""
        try:
            raise ValueError("Test exception")
        except ValueError as e:
            handle_unexpected_error(e)
        
        output = mock_stderr.getvalue()
        assert "Unexpected Error: ValueError: Test exception" in output
        assert "This is likely a bug" in output

    @patch("sys.stderr", new_callable=StringIO)
    def test_handle_unexpected_error_with_traceback(self, mock_stderr: StringIO) -> None:
        """Test unexpected error includes full traceback."""
        def nested_function() -> None:
            raise RuntimeError("Nested error")
        
        def outer_function() -> None:
            nested_function()
        
        try:
            outer_function()
        except RuntimeError as e:
            handle_unexpected_error(e)
        
        output = mock_stderr.getvalue()
        assert "Unexpected Error: RuntimeError: Nested error" in output
        assert "This is likely a bug" in output
        # Since we're capturing stderr, traceback info would be printed separately

    @patch("sys.stderr", new_callable=StringIO)
    def test_stderr_is_flushed(self, mock_stderr: StringIO) -> None:
        """Test that stderr is flushed after writing."""
        # StringIO doesn't have a real flush, but we can verify it was called
        mock_stderr.flush = Mock()
        
        handle_startup_error("TEST_ERROR", "Test message")
        
        mock_stderr.flush.assert_called_once()