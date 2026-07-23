import pytest
from time import sleep
from loguru import logger
from conftest import MOCK_ROKU_STATE
from app_configs import AppTestConfig  # Import your config class

PAUSE_TIME = 5
MAX_WAIT_TIME = 30

# Define your provider test data sets here
PROVIDERS = [
    AppTestConfig(app_id="12", app_name="Netflix", content_id="81556391", content_type="series"),
    AppTestConfig(app_id="674313", app_name="Zinnia TV", content_id="3301125", content_type="video"),
    # Easy to add others later:
    # AppTestConfig(app_id="837", app_name="YouTube", content_id="dQw4w9WgXcQ", content_type="live"),
]

@pytest.mark.parametrize("provider", PROVIDERS, ids=lambda p: p.app_name.lower())
def test_app_launch_and_playback_workflow(client, is_hw, manual_confirmation, provider: AppTestConfig):
    """
    Validates that a deep link can be triggered on any streaming application 
    and verifies that state monitoring parses the player states correctly.
    """

    def hw_sleep(s: int):
        if is_hw:
            sleep(s)

    def get_state() -> str:
        response = client.get("/get-state")
        assert response.status_code == 200
        return response.json()[0]

    def wait_until(target_state: str, max_sleep: int) -> bool:
        for _ in range(max_sleep):
            if get_state() == target_state:
                return True
            logger.info("Waiting for state change")
            hw_sleep(1)
        return get_state() == target_state

    def confirmation(msg: str, s: int):
        if not is_hw:
            return True
        if manual_confirmation:
            print("\n\n--- 📺 MANUAL CONFIRMATION REQUIRED ---")
            user_input = input(f"\nPlease confirm: {msg} (y/n): ").strip().lower()
            return user_input == 'y'
        sleep(s)
        return True

    # --- Arrange: Mock Mode Setup using the active provider ---
    if not is_hw:
        MOCK_ROKU_STATE["plugin_id"] = [provider.app_id]
        MOCK_ROKU_STATE["plugin_name"] = [provider.app_name]
        MOCK_ROKU_STATE["player_state"] = ["play", "pause", "play", "play"]
        MOCK_ROKU_STATE["app_state"] = f"""
            <active-app>
                <app id="{provider.app_id}" type="appl" version="80.2523.1521022" ui-location="{provider.app_id}">{provider.app_name}</app>
            </active-app>
            """

    launch_payload = {
        "app_id": provider.app_id,
        "content_id": provider.content_id,
        "content_type": provider.content_type
    }

    # 1. Launch & verify play
    launch_response = client.post("launch", json=launch_payload)
    if launch_response.status_code == 422:
        logger.error("\nVALIDATION ERROR DETAILS:", launch_response.json())
    assert launch_response.status_code == 200
    assert "Launch successful:" in launch_response.json()["message"]

    assert confirmation(f"Did {provider.app_name} launch?", PAUSE_TIME) is True
    assert wait_until("play", MAX_WAIT_TIME)

    active_app_response = client.get("/get-active-app")
    assert active_app_response.status_code == 200
    active_app = active_app_response.json()
    assert active_app["@id"] == provider.app_id
    assert active_app["#text"] == provider.app_name

    # 2. Pause
    hw_sleep(PAUSE_TIME)
    pause_response = client.post("press/Play")
    assert pause_response.status_code == 200
    assert confirmation("Did the show pause?", PAUSE_TIME) is True
    assert wait_until("pause", MAX_WAIT_TIME)

    # 3. Play
    play_response = client.post("press/Play")
    assert play_response.status_code == 200
    assert confirmation("Did the show play?", PAUSE_TIME) is True
    assert wait_until("play", MAX_WAIT_TIME)

    # 4. Restart
    restart_response = client.post("restart", json={"pause": "false"})
    assert restart_response.status_code == 200
    assert confirmation("Did the show restart?", PAUSE_TIME) is True
    assert wait_until("play", MAX_WAIT_TIME)

    hw_sleep(PAUSE_TIME)