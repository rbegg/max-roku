import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from http import HTTPStatus

from max_roku.roku_controller import RokuController, Command

@pytest.fixture
def mock_client():
    """Mocks the httpx.AsyncClient."""
    return AsyncMock()

@pytest.fixture
def controller(mock_client):
    """Provides a RokuController instance with a mocked HTTP client."""
    return RokuController("192.168.1.50", client=mock_client)

@pytest.mark.asyncio
async def test_send_command_success(controller, mock_client):
    """Verify send_command constructs the correct URL and performs a POST."""
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_client.post.return_value = mock_response

    # Act
    await controller.send_command(Command.HOME)

    # Assert
    expected_url = "http://192.168.1.50:8060/keypress/Home"
    mock_client.post.assert_called_once_with(expected_url)

@pytest.mark.asyncio
async def test_get_media_player_state_success(controller, mock_client):
    """Verify get_full_state parses the XML response correctly."""
    # Arrange
    xml_response = """
    <player state="play">
        <position>10000</position>
        <plugin>Netflix</plugin>
    </player>
    """
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.text = xml_response
    mock_client.get.return_value = mock_response

    # Act
    state, raw = await controller.get_media_player_state()

    # Assert
    assert state == "play"
    assert raw["player"]["plugin"] == "Netflix"
    mock_client.get.assert_called_once()

@pytest.mark.asyncio
async def test_get_media_player_state_failure(controller, mock_client):
    """Verify that a non-200 response returns None."""
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.NOT_FOUND
    mock_client.get.return_value = mock_response

    # Act
    state, raw = await controller.get_media_player_state()

    # Assert
    assert state is None
    assert raw is None

# @pytest.mark.asyncio
# async def test_send_command_failure(controller, mock_client):
#     """Verify that send_command handles non-200 status codes."""
#     # Arrange
#     mock_response = MagicMock()
#     mock_response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
#     mock_client.post.return_value = mock_response
#
#     # Act
#     # Assuming your implementation raises an exception or returns a specific value
#     # Adjust based on how your controller handles this
#     with pytest.raises(Exception):
#         await controller.send_command(Command.HOME)

@pytest.mark.asyncio
async def test_get_media_player_state_unknown_state(controller, mock_client):
    """Verify state mapping handles unknown states correctly."""
    # Arrange: Simulate an unknown state returned from Roku
    xml_response = '<player state="rebooting"></player>'
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.text = xml_response
    mock_client.get.return_value = mock_response

    # Act
    state, _ = await controller.get_media_player_state()

    # Assert: Depending on your controller, it might default to 'stop' or None
    assert state == "unknown"  # or whatever your default 'else' logic is

@pytest.mark.asyncio
async def test_get_media_player_state_exception(controller, mock_client):
    """Verify that network exceptions are caught."""
    # Arrange
    mock_client.get.side_effect = Exception("Network Connection Refused")

    # Act
    state, raw = await controller.get_media_player_state()

    # Assert
    assert state is None
    assert raw is None


@pytest.mark.asyncio
async def test_get_media_player_state_exception(controller, mock_client):
    """Verify that network exceptions are caught."""
    # Arrange
    mock_client.get.side_effect = Exception("Network Connection Refused")

    # Act
    state, raw = await controller.get_media_player_state()

    # Assert
    assert state is None
    assert raw is None


# In roku_controller.py

async def test_press_until_playing(controller, mock_client) -> bool:

    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_client.post.return_value = mock_response

    controller.get_media_player_state = AsyncMock()
    controller.get_media_player_state.side_effect = [
        ("stop", {"player": {"@state": "stop"}}),
        ("pause", {"player": {"@state": "pause"}}),
        ("play", {"player": {"@state": "play"}})
    ]
    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:

            # Act
        state = await controller.press_until_playing(max_retries=10)

        # Assert
        assert state is True
