import os
import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from max_roku.main import roku_app, get_controller

# Ensure this runs once per test session
os.environ["ROKU_IP"] = "127.0.0.1"


@pytest.fixture
def mock_roku():
    """Creates a fresh, isolated mock for every single test."""
    return AsyncMock()


@pytest.fixture
def client(mock_roku):
    """Sets up the TestClient with the mocked dependency."""

    def override_get_controller():
        return mock_roku

    roku_app.dependency_overrides[get_controller] = override_get_controller

    with TestClient(roku_app) as test_client:
        yield test_client

    roku_app.dependency_overrides.clear()

@pytest.fixture
def mock_controller():
    """Provides a fresh controller mock for unit tests."""
    mock = AsyncMock()
    # Common mock setup for successful responses
    mock.launch_app = AsyncMock(return_value=True)
    mock.press_until_playing = AsyncMock(return_value=True)
    mock.get_media_player_state = AsyncMock(return_value=("play", {"player": {"@state": "play"}}))
    mock._state = "play"
    return mock