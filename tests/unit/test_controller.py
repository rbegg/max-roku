import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock
from http import HTTPStatus

from max_roku.exceptions import RokuUnexpectedState, RokuConnectionError, RokuCommandError
from max_roku.roku_controller import RokuController, Command

@pytest.fixture
def mock_client():
    """Mocks the httpx.AsyncClient."""
    return AsyncMock()

@pytest.fixture
def controller(mock_client):
    """Provides a RokuController instance with a mocked HTTP client."""
    return RokuController("localhost", client=mock_client)

@pytest.mark.asyncio
async def test_send_command_success(controller, mock_client):
    """Verify send_command constructs the correct URL and performs a POST."""
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_client.post.return_value = mock_response

    # Act
    try:
        await controller.send_command(Command.HOME)
    except Exception as e:
        pytest.fail(f"Send command raised an unexpected exception: {e}")

    # Assert
    expected_url = "http://localhost:8060/keypress/Home"
    mock_client.post.assert_called_once_with(expected_url)

@pytest.mark.asyncio
async def test_get_media_player_state_success(controller, mock_client):
    """Verify get_full_state parses the XML response correctly."""
    # Arrange
    xml_template = """
    <player state="{}">
        <position>10000</position>
        <plugin>Netflix</plugin>
    </player>
    """
    test_states = [
        ("play", "play"),
        ("pause", "pause"),
        ("buffering", "play"),
        ("stop", "stop"),
        ("error", "unknown"),
        ("incorrect", "unknown"),
    ]
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.OK

    for mock_state, expected_state in test_states:
        xml_response = xml_template.format(mock_state)
        mock_response.text = xml_response
        mock_client.get.return_value = mock_response

        # Act
        state, raw = await controller.get_media_player_state()

        # Assert
        assert state == expected_state
        assert raw is not None
        assert raw["player"]["plugin"] == "Netflix"


@pytest.mark.asyncio
async def test_get_media_player_state_failure(controller, mock_client):
    """Verify that a non-200 response returns None."""
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.NOT_FOUND
    mock_response.text = ""
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Not Found", request=MagicMock(), response=mock_response
    )
    mock_client.get.return_value = mock_response

    # Act & Assert
    with pytest.raises(RokuUnexpectedState):
        await controller.get_media_player_state()


@pytest.mark.asyncio
async def test_send_command_failure(controller, mock_client):
    """Verify that send_command handles non-200 status codes."""
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        message="Internal Server Error",
        request=MagicMock(),
        response=mock_response
    )
    mock_client.post.return_value = mock_response

    # Act & Assert
    with pytest.raises(RokuCommandError,match="Roku rejected command 'Back'"):
        await controller.send_command(Command.BACK)

    # Assert
    expected_url = "http://localhost:8060/keypress/Back"
    mock_client.post.assert_called_once_with(expected_url)


@pytest.mark.asyncio
async def test_send_command_exception(controller, mock_client):
    """Verify that send_command handles non-200 status codes."""
    # Arrange
    mock_client.post.side_effect = httpx.ConnectError("Network Connection Refused")

    # Act & Assert
    with pytest.raises(RokuConnectionError) as exc_info:
        await controller.send_command(Command.UP)
        assert "DeviceUnavailable" == str(exc_info.value)

    # Assert
    expected_url = "http://localhost:8060/keypress/Up"
    mock_client.post.assert_called_once_with(expected_url)


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

    mock_client.get.side_effect = httpx.ConnectError("Network Connection Refused")

    # Act
    with pytest.raises(RokuConnectionError, match="Failed to communicate with Roku device"):
        await controller.get_media_player_state()



async def test_press_until_playing(controller, mock_client):

    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_client.post.return_value = mock_response

    controller.get_media_player_state = AsyncMock()
    controller.get_media_player_state.side_effect = [
        ("stop", {"player": {"@state": "stop"}}),
        ("play", {"player": {"@state": "play"}}),
    ]

    # Act
    state = await controller.press_until_playing(max_retries=10)

    # Assert
    assert state is True


async def test_launch_success(controller, mock_client):
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_client.post.return_value = mock_response

    # Act
    await controller.launch_app("123", "456", "Movie")

    # Assert
    expected_url = "http://localhost:8060/launch/123"
    expected_params = {'contentId': '456', 'mediaType': 'Movie'}
    mock_client.post.assert_called_once_with(expected_url, params=expected_params)


async def test_launch_error(controller, mock_client):
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    mock_client.post.return_value = mock_response

    # Act
    await controller.launch_app("123", "456", "Movie")

    # Assert
    expected_url = "http://localhost:8060/launch/123"
    expected_params = {'contentId': '456', 'mediaType': 'Movie'}
    mock_client.post.assert_called_once_with(expected_url, params=expected_params)


async def test_launch_exception(controller, mock_client):
    # Arrange
    mock_client.post.side_effect = httpx.ConnectError("Network Connection Refused")

    # Act & Assert
    with pytest.raises(RokuConnectionError, match="Failed to communicate with Roku device"):
        _ = await controller.launch_app("123", "456", "Movie")


async def test_get_active_app_success(controller, mock_client):
    # Arrange
    mock_xml = """
    <active-app>
        <app id="12" type="appl" version="4.1.218">Netflix</app>
    </active-app>
    """
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.text = mock_xml
    mock_client.get.return_value = mock_response

    # Act
    active_app = await controller.get_active_app()

    # Assert
    assert active_app is not None
    assert active_app['@id']      == '12'
    assert active_app['@type']    == 'appl'
    assert active_app['@version'] == '4.1.218'
    assert active_app['#text']    == 'Netflix'
    expected_url = "http://localhost:8060/query/active-app"
    mock_client.get.assert_called_once_with(expected_url)


async def test_get_active_app_error(controller, mock_client):
    """
    Verify that get_active_app returns None when an error state is returned.
    """
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        message="Internal Server Error",
        request=MagicMock(),
        response=mock_response
    )
    mock_response.text = ""
    mock_client.get.return_value = mock_response

    # Act & Access
    with pytest.raises(RokuCommandError, match="Roku rejected '/query/active-app' with status"):
        _ = await controller.get_active_app()


async def test_get_active_app_exception(controller, mock_client):
    """
    Verify that get_active_app returns None when an exception is raised.
    """
    # Arrange
    mock_client.get.side_effect = httpx.ConnectError("Network Connection Refused")

    # Act & Access
    with pytest.raises(RokuConnectionError, match="Failed to communicate with Roku device"):
        _ = await controller.get_active_app()
