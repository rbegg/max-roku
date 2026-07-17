import os
import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from max_roku.main import roku_app, get_controller

# Ensure this runs once per test session
os.environ["ROKU_IP"] = "localhost"


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
    mock.get_active_app = (
        AsyncMock(return_value={"@id":"12", "@type": "appl", "@version": "4.1.218", "#text":"Netflix"})
    )
    mock._state = "play"
    return mock


@pytest.fixture
def override_provider():
    """
    Fixture factory to quickly swap out get_provider with a configured AsyncMock.
    Cleans up overrides automatically after the test finishes.
    """
    from max_roku.main import roku_app, get_current_provider

    mock_provider = AsyncMock()

    def _override(side_effect=None, return_value=None):
        if side_effect:
            mock_provider.launch.side_effect = side_effect
            mock_provider.restart.side_effect = side_effect
            mock_provider.post.side_effect = side_effect
        else:
            mock_provider.launch.return_value = return_value
            mock_provider.restart.return_value = return_value
            mock_provider.post.return_value = return_value

        roku_app.dependency_overrides[get_current_provider] = lambda: mock_provider
        return mock_provider

    yield _override

    # Teardown block runs automatically when the test finishes
    if get_current_provider in roku_app.dependency_overrides:
        del roku_app.dependency_overrides[get_current_provider]