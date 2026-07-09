import os
from contextlib import contextmanager
from http import HTTPStatus

from unittest.mock import AsyncMock, patch

from max_roku.exceptions import RokuCommandError, RokuConnectionError, RokuParsingError
from max_roku.main import get_provider, roku_app
from fastapi.testclient import TestClient


# 1. Block the network call before the app imports
os.environ["ROKU_IP"] = "127.0.0.1"


@contextmanager
def mock_get_provider(side_effect=None, return_value=None):
    """
    Context manager helper to override the get_provider dependency
    for the duration of a specific 'with' block.
    """
    mock_provider = AsyncMock()

    if side_effect:
        mock_provider.post.side_effect = side_effect
        mock_provider.launch.side_effect = side_effect
    else:
        mock_provider.post.return_value = return_value
        mock_provider.launch.return_value = return_value

    # Temporarily override the dependency token in FastAPI's map
    roku_app.dependency_overrides[get_provider] = lambda: mock_provider
    try:
        yield mock_provider
    finally:
        # Guarantee cleanup when exiting the 'with' block context
        if get_provider in roku_app.dependency_overrides:
            del roku_app.dependency_overrides[get_provider]

# --- Tests ---
def test_get_controller_dependency(client):
    """
    Verify that the get_controller dependency returns an instance
    of RokuController from the app state.
    """
    # Note: 'client' is the fixture defined in your conftest.py,
    # which sets up the dependency override.

    # We can test this by checking the application state through the client's app
    from max_roku.main import roku_app, RokuController

    # Access the app state directly
    controller = roku_app.state.controller

    assert isinstance(controller, RokuController)
    assert controller is not None





def test_lifespan_discovery_success():
    """
    Test that lifespan works even without ROKU_IP
    by mocking the discovery process.
    """
    # 1. Arrange: Patch the discovery function in the 'main' module
    # We force it to return a fake IP instead of scanning the network
    with patch("max_roku.main.discover_roku_ip", return_value="127.0.0.1"):
        # 2. Act: Trigger the lifespan by creating the TestClient
        # Note: We ensure ROKU_IP is NOT set in the environment
        with patch.dict("os.environ", {"ROKU_IP": ""}, clear=True):
            with TestClient(roku_app):
                # 3. Assert: Verify the app started and state was set
                assert roku_app.state.controller is not None
                print("Lifespan started successfully with mocked IP")

def test_get_status_success(client, mock_roku):
    """Test that the status endpoint correctly formats the player state."""

    # Arrange
    mock_roku.get_media_player_state.return_value = {"player": {"@state": "play"}}

    # Act
    response = client.get("/get-state")

    # Assert
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"player": {"@state": "play"}}
    mock_roku.get_media_player_state.assert_called_once()


def test_press_command_success(client, mock_roku):
    """Test that valid ECP commands are successfully sent to the controller."""

    # Act
    response = client.post("/press/Home")

    # Assert
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"message": "Command Home sent successfully"}
    mock_roku.send_command.assert_called_once()

def test_restart_success(client, override_provider):
    """Test restart command to replay current content from the start"""

    # Act
    response = client.post("/restart", json={"pause": "false"})

    # Assert
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"message": "Restart command sent"}


def test_get_status_failure(override_provider, client, mock_roku):
    """Test handling when the Roku device returns a 500 error or is unreachable."""
    # Arrange: Mock the controller to return None (indicating failure)
    mock_roku.get_media_player_state.side_effect=RokuConnectionError("Can't connect to Roku Device:")

    # Act
    response = client.get("/get-state")

    # Assert
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE


# Assuming your setup remains the same with the client fixture

def test_launch_app_success(client, mock_roku):
    """Test successful deep link launch."""
    # Arrange

    # Act
    response = client.post("/launch", json={"app_id": "12", "content_id": "123"})

    # Assert
    assert response.status_code == HTTPStatus.OK
    assert "Launch successful:" in response.json()["message"]


def test_launch_app_failure(override_provider, client, mock_roku):
    """Test behavior when the provider fails to launch due to a domain exception."""

    override_provider(side_effect=RokuCommandError("Command rejected:"))

    # Act
    response = client.post("/launch", json={"app_id": "999", "content_id": "123"})

    # Assert
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Command rejected:" in response.json()["detail"]


def test_restart_player_failure(override_provider, client):
    """Test restart endpoint when the controller fails."""

    override_provider(side_effect=RokuParsingError("Cannot parse result:"))
    # Act
    response = client.post("/restart", json={"pause": True})

    # Assert
    assert response.status_code == HTTPStatus.BAD_GATEWAY
    assert "Cannot parse result:" in response.json()["detail"]

def test_press_command_unsupported(client, mock_roku):
    """Test that an invalid command returns a 400 Bad Request."""

    # Act
    response = client.post("/press/invalid_button")

    # Assert
    assert response.status_code == 422
    # Verify the controller was never actually called
    mock_roku.send_command.assert_not_called()

def test_get_active_app_success(client, mock_roku):

    # Arrange
    mock_dict = {"@id":"12", "@type": "appl", "@version": "4.1.218", "#text":"Netflix"}

    mock_roku.get_active_app.return_value = mock_dict

    # Act
    response = client.get("/get-active-app")

    # Assert
    assert response.status_code == 200
    assert response.json() == mock_dict
    mock_roku.get_active_app.assert_called_once()