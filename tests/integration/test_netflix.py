from time import sleep
from loguru import logger

from conftest import MOCK_ROKU_STATE

PAUSE_TIME = 5
MAX_WAIT_TIME = 30


def test_launch_netflix_and_verify_playing(client, is_hw, manual_confirmation):
    """
    Validates that a movie deep link can be triggered on Netflix andy
    proves the application correctly handles state monitoring parsing.
    """

    def hw_sleep(s: int):
        """ Helper function to sleep for a given number of seconds if in hardware mode. """
        if is_hw:
            sleep(s)


    def get_state() -> str:
        response = client.get("/get-state")

        assert response.status_code == 200
        data = response.json()
        s = data[0]
        return s

    def wait_until(target_state: str, max_sleep: int) -> bool:
        """ helper function to sleep for up to max seconds waiting for a given state """

        for i in range(max_sleep):
            s = get_state()
            if s == target_state:
                return True
            hw_sleep(1)

        return get_state() == target_state


    def confirmation(msg: str, s: int):
        if not is_hw:
            return True

        if manual_confirmation:
            print("\n\n--- 📺 MANUAL CONFIRMATION REQUIRED ---")
            user_input = input(f"\nPlease confirm: {msg} (y/n): ").strip().lower()
            return user_input == 'y'

        # without manual confirmation, a sleep is required to allow the player time to complete action
        sleep(s)
        return True


    # --- Arrange: If we're in Mock Mode, program our network timeline sequence ---
    if not is_hw:
        # Scenario Timeline:
        # Setup: App initiates launch -> returns 200 OK
        # Check: App hits /get-active-app -> returns Netflix with 'play' state tracking
        MOCK_ROKU_STATE["plugin_id"] = ["12"]
        MOCK_ROKU_STATE["plugin_name"] = ["Netflix"]
        MOCK_ROKU_STATE["player_state"] = ["play", "pause", "play"]

    # --- Act: Fire the request against your FastAPI rest client route ---
    launch_payload = {
        "app_id": "12",
        "content_id": "81556391",  # Example Netflix movie asset ID
        "content_type": "series"
    }

    # 1. Launch & verify play
    launch_response = client.post("launch", json=launch_payload)
    if launch_response.status_code == 422:
        logger.error("\nVALIDATION ERROR DETAILS:", launch_response.json())
    assert launch_response.status_code == 200
    assert "Launch successful:" in launch_response.json()["message"]

    assert confirmation("Did the show launch?", PAUSE_TIME) is True
    assert wait_until("play", MAX_WAIT_TIME)

    active_app_response = client.get("/get-active-app")
    if active_app_response.status_code == 422:
        logger.error("\nVALIDATION ERROR DETAILS:", active_app_response.json())
    assert active_app_response.status_code == 200
    active_app = active_app_response.json()
    assert active_app["@id"] == "12"
    assert active_app["#text"] == "Netflix"

    # 2. Pause
    pause_response = client.post("press/Play",)
    assert pause_response.status_code == 200
    assert pause_response.json() == {"message": "Command Play sent successfully"}

    assert confirmation("Did the show pause?", PAUSE_TIME) is True
    assert wait_until("pause", MAX_WAIT_TIME)

    # 3. Play
    play_response = client.post("press/Play", )
    assert play_response.status_code == 200
    assert play_response.json() == {"message": "Command Play sent successfully"}
    assert confirmation("Did the show play?", PAUSE_TIME) is True
    assert wait_until("play", MAX_WAIT_TIME)


    #5. Restart

    restart_response = client.post("restart", json={"pause": "false"})
    assert restart_response.status_code == 200
    assert restart_response.json() == {"message": "Restart command sent"}

    assert confirmation("Did the show restart?", PAUSE_TIME) is True
    assert wait_until("play", MAX_WAIT_TIME)

