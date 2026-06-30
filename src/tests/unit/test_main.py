import os
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

# 1. Block the network call before the app imports
os.environ["ROKU_IP"] = "127.0.0.1"


# --- Tests ---

def test_get_status_success(client, mock_roku):
    """Test that the status endpoint correctly formats the player state."""

    # Arrange
    mock_roku.get_media_player_state.return_value = {"player": {"@state": "play"}}

    # Act
    response = client.get("/status")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"player": {"@state": "play"}}
    mock_roku.get_media_player_state.assert_called_once()


def test_press_command_success(client, mock_roku):
    """Test that valid ECP commands are successfully sent to the controller."""

    # Act
    response = client.post("/press/home")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": "Command Home sent successfully"}
    mock_roku.send_command.assert_called_once()

def test_restart_success(client, mock_roku):
    """Test restart command to replay current content from the start"""

    # Act
    response = client.post("/restart", json={"pause": "false"})

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": "Restart command sent"}
    mock_roku.restart_current.assert_called_once()


def test_press_command_unsupported(client, mock_roku):
    """Test that an invalid command returns a 400 Bad Request."""

    # Act
    response = client.post("/press/invalid_button")

    # Assert
    assert response.status_code == 400
    assert "not supported" in response.json()["detail"]
    # Verify the controller was never actually called
    mock_roku.send_command.assert_not_called()

    import pytest
    from unittest.mock import AsyncMock, patch
    from fastapi import HTTPException

# Assuming your setup remains the same with the client fixture
def test_get_status_failure(client, mock_roku):
    """Test handling when the Roku device returns a 500 error or is unreachable."""
    # Arrange: Mock the controller to return None (indicating failure)
    mock_roku.get_media_player_state.return_value = None

    # Act
    response = client.get("/status")

    # Assert
    assert response.status_code == 500  # Or adjust based on how main.py handles None
    assert "Failed to fetch state" in response.json()["detail"]

def test_launch_app_success(client, mock_roku):
    """Test successful deep link launch."""
    # We don't need to mock the provider directly if we want an integration test
    # but we can mock the controller behavior the provider depends on.

    # Act
    response = client.post("/launch", json={"app_id": "12", "content_id": "123"})

    # Assert
    assert response.status_code == 200
    assert "launched successfully" in response.json()["message"]

def test_launch_app_failure(client, mock_roku):
    """Test behavior when the provider fails to launch."""
    # Use patch to force the provider's launch method to return False
    with patch("max_roku.main.get_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.launch.return_value = False
        mock_get_provider.return_value = mock_provider

        # Act
        response = client.post("/launch", json={"app_id": "999", "content_id": "123"})

        # Assert
        assert response.status_code == 500
        assert "Failed to launch app" in response.json()["detail"]

def test_restart_player_failure(client, mock_roku):
    """Test restart endpoint when the controller fails."""
    # Arrange
    mock_roku.restart_current.return_value = False

    # Act
    response = client.post("/restart", json={"pause": True})

    # Assert
    assert response.status_code == 500
    assert "Failed to restart" in response.json()["detail"]