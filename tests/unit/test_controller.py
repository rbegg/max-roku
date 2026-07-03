import httpx
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
    return RokuController("localhost", client=mock_client)

@pytest.mark.asyncio
async def test_send_command_success(controller, mock_client):
    """Verify send_command constructs the correct URL and performs a POST."""
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_client.post.return_value = mock_response

    # Act
    success = await controller.send_command(Command.HOME)

    # Assert
    assert success
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
    mock_client.get.return_value = mock_response

    # Act
    state, raw = await controller.get_media_player_state()

    # Assert
    assert state is None
    assert raw is None

@pytest.mark.asyncio
async def test_send_command_failure(controller, mock_client):
    """Verify that send_command handles non-200 status codes."""
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    mock_client.post.return_value = mock_response

    # Act
    # Assuming your implementation raises an exception or returns a specific value
    # Adjust based on how your controller handles this
    success = await controller.send_command(Command.BACK)

    # Assert
    assert not success
    expected_url = "http://localhost:8060/keypress/Back"
    mock_client.post.assert_called_once_with(expected_url)

@pytest.mark.asyncio
async def test_send_command_exception(controller, mock_client):
    """Verify that send_command handles non-200 status codes."""
    # Arrange
    mock_client.post.side_effect = httpx.ConnectError("Network Connection Refused")

    # Act
    success = await controller.send_command(Command.UP)

    # Assert
    assert not success
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
    state, raw = await controller.get_media_player_state()

    # Assert
    assert state is None
    assert raw is None


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
    success = await controller.launch_app("123", "456", "Movie")

    # Assert
    assert success
    expected_url = "http://localhost:8060/launch/123"
    expected_params = {'contentID': '456', 'mediaType': 'Movie'}
    mock_client.post.assert_called_once_with(expected_url, params=expected_params)


async def test_launch_error(controller, mock_client):
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    mock_client.post.return_value = mock_response

    # Act
    success = await controller.launch_app("123", "456", "Movie")

    # Assert
    assert not success
    expected_url = "http://localhost:8060/launch/123"
    expected_params = {'contentID': '456', 'mediaType': 'Movie'}
    mock_client.post.assert_called_once_with(expected_url, params=expected_params)


async def test_launch_exception(controller, mock_client):
    # Arrange
    mock_client.post.side_effect = httpx.ConnectError("Network Connection Refused")

    # Act
    success = await controller.launch_app("123", "456", "Movie")

    # Assert
    assert not success


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
    mock_client.get.return_value = mock_response

    # Act
    active_app = await controller.get_active_app()

    # Assert
    assert active_app is None


async def test_get_active_app_exception(controller, mock_client):
    """
    Verify that get_active_app returns None when an exception is raised.
    """
    # Arrange
    mock_client.get.side_effect = Exception("Network Connection Refused")

    # Act
    active_app = await controller.get_active_app()

    # Assert
    assert active_app is None


@pytest.mark.asyncio
async def test_restart_current(controller, mock_client):
    """Verify that restart_current delegates to the provider when the state is valid."""
    # Arrange
    # 1. Mock the state to be 'play' so the controller proceeds
    # controller.get_media_player_state = AsyncMock(return_value=("play", {"player": {"plugin": {"@id": "123"}}}))
    xml_response = """
    <player state="play">
        <position>10000</position>
        <plugin id="123" name="Netflix" type="appl" />
    </player>
    """
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.text = xml_response
    mock_client.get.return_value = mock_response

    # 2. Mock the provider factory and the provider itself
    with patch("max_roku.roku_controller.get_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.restart = AsyncMock(return_value=True)
        mock_get_provider.return_value = mock_provider

        # Act
        success = await controller.restart_current(pause=False)

        # Assert
        assert success is True
        mock_provider.restart.assert_called_once_with(False)