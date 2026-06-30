import pytest
from unittest.mock import AsyncMock
from max_roku.provider import get_provider, NetflixProvider, ZinniaProvider, GenericProvider


# --- Factory Tests ---

@pytest.mark.asyncio
async def test_get_provider_resolution():
    """Verify the factory correctly resolves the right class."""
    controller = AsyncMock()
    assert isinstance(get_provider("12", controller), NetflixProvider)
    assert isinstance(get_provider("674313", controller), ZinniaProvider)
    assert isinstance(get_provider("99999", controller), GenericProvider)

# --- Netflix Provider Tests ---

@pytest.mark.asyncio
async def test_netflix_launch(mock_controller):
    provider = NetflixProvider(mock_controller)
    success = await provider.launch(content_id="123")
    assert success is True

@pytest.mark.asyncio
async def test_netflix_launch_false(mock_controller):
    mock_controller.get_media_player_state = AsyncMock(return_value=("stop", {"player": {"@state": "stop"}}))
    mock_controller.press_until_playing = AsyncMock(return_value=False)
    provider = NetflixProvider(mock_controller)
    success = await provider.launch(content_id="123")
    assert success is False

@pytest.mark.asyncio
async def test_netflix_restart(mock_controller):
    provider = NetflixProvider(mock_controller)
    mock_controller.position = 35000

    success = await provider.restart(pause=False)
    assert success is True
    assert mock_controller.send_command.call_count >= 3

@pytest.mark.asyncio
async def test_netflix_restart_fwd(mock_controller):
    provider = NetflixProvider(mock_controller)
    mock_controller.position = 34000

    success = await provider.restart(pause=True)
    assert success is True
    assert mock_controller.send_command.call_count >= 5

@pytest.mark.asyncio
async def test_netflix_pause(mock_controller):
    provider = NetflixProvider(mock_controller)
    mock_controller.get_media_player_state.side_effect = [
        ("play", {"player": {"@state": "play"}}),
        ("pause", {"player": {"@state": "pause"}})
    ]
    state = await provider.pause()
    assert state == "pause"
    assert mock_controller.get_media_player_state.call_count == 2

# --- Zinnia Provider Tests ---

@pytest.mark.asyncio
async def test_zinnia_launch(mock_controller):
    provider = ZinniaProvider(mock_controller)
    success = await provider.launch(content_id="456")
    assert success is True

@pytest.mark.asyncio
async def test_zinnia_restart_pause(mock_controller):
    provider = ZinniaProvider(mock_controller)
    mock_controller.state = "play"
    mock_controller.position = 5000
    success = await provider.restart(pause=True)
    assert success is True

@pytest.mark.asyncio
async def test_zinnia_restart_nopause(mock_controller):
    provider = ZinniaProvider(mock_controller)
    mock_controller.state = "play"
    mock_controller.position = 4000
    success = await provider.restart(pause=False)
    assert success is True

@pytest.mark.asyncio
async def test_zinnia_pause(mock_controller):
    mock_controller.get_media_player_state = AsyncMock(return_value=("pause", {"player": {"@state": "pause"}}))
    provider = ZinniaProvider(mock_controller)
    mock_controller.state = "pause"
    state = await provider.pause()
    assert state == "pause"
    assert mock_controller.get_media_player_state.call_count == 1

# --- Generic Provider Tests ---

@pytest.mark.asyncio
async def test_generic_launch(mock_controller):
    provider = GenericProvider(mock_controller, app_id="123")
    success = await provider.launch(content_id="789")
    assert success is True

@pytest.mark.asyncio
async def test_generic_restart(mock_controller):
    provider = GenericProvider(mock_controller, app_id="123")
    mock_controller.state = "play"
    mock_controller.position = 10000
    success = await provider.restart(pause=False)
    assert success is False