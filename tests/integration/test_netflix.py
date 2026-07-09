from time import sleep
from loguru import logger

from conftest import MOCK_ROKU_STATE



def confirmation(msg: str):
    print("\n\n--- 📺 MANUAL CONFIRMATION REQUIRED ---")

    user_input = input(f"\nPlease confirm: {msg} (y/n): ").strip().lower()
    return user_input == 'y'


def test_launch_netflix_and_verify_playing(client, is_hw, manual_confirmation):
    """
    Validates that a movie deep link can be triggered on Netflix andy
    proves the application correctly handles state monitoring parsing.
    """
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

    # 1. Launch
    launch_response = client.post("launch", json=launch_payload)
    if launch_response.status_code == 422:
        logger.error("\nVALIDATION ERROR DETAILS:", launch_response.json())
    assert launch_response.status_code == 200
    assert "Launch successful:" in launch_response.json()["message"]

    sleep(5)

    # 2. Verify state = play
    state_response = client.get("/get-state")

    assert state_response.status_code == 200
    response_data = state_response.json()
    state = response_data[0]
    assert state == "play"
    assert "Netflix" in str(state_response.json())

    if is_hw and manual_confirmation:
        assert confirmation("Did the show launch?") is True
    else:
        sleep(5)

    # 3. Pause
    pause_response = client.post("press/Play",)
    assert pause_response.status_code == 200
    assert pause_response.json() == {"message": "Command Play sent successfully"}
    sleep(5)

    state_response = client.get("/get-state")

    assert state_response.status_code == 200
    response_data = state_response.json()
    state = response_data[0]
    assert state == "pause"

    if is_hw and manual_confirmation:
        assert confirmation("Did the show pause?") is True
    else:
        sleep(5)

    # 4. Play
    play_response = client.post("press/Play", )
    assert play_response.status_code == 200
    assert play_response.json() == {"message": "Command Play sent successfully"}
    sleep(5)

    state_response = client.get("/get-state")

    assert state_response.status_code == 200
    response_data = state_response.json()
    state = response_data[0]
    assert state == "play"

    if is_hw and manual_confirmation:
        assert confirmation("Did the show play?") is True
    else:
        sleep(5)

    #5. Restart

    restart_response = client.post("restart", json={"pause": "false"})
    assert restart_response.status_code == 200
    assert restart_response.json() == {"message": "Restart command sent"}

    if is_hw and manual_confirmation:
        assert confirmation("Did the show restart?")

