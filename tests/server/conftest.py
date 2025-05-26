"""Configuration specific to server tests."""

import logging
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _suppress_logging(monkeypatch) -> None:
    """Suppress all logging output in tests."""
    # Override structlog.configure to do nothing
    monkeypatch.setattr("structlog.configure", lambda *args, **kwargs: None)

    # Override structlog.get_logger to return a mock that does nothing
    mock_logger = MagicMock()
    mock_logger.info = MagicMock()
    mock_logger.warning = MagicMock()
    mock_logger.error = MagicMock()
    mock_logger.debug = MagicMock()
    monkeypatch.setattr("structlog.get_logger", lambda *args, **kwargs: mock_logger)

    # Create a proper StreamHandler replacement that accepts the same arguments
    class SilentStreamHandler(logging.Handler):
        def __init__(self, stream=None) -> None:
            # Accept stream parameter but ignore it
            super().__init__()

        def emit(self, record) -> None:
            # Do nothing - suppress all output
            pass

    monkeypatch.setattr("logging.StreamHandler", SilentStreamHandler)

