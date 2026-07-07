import asyncio
from loguru import logger

from conftest import MOCK_ROKU_STATE



def confirmation(msg: str):
    print("\n\n--- 📺 MANUAL CONFIRMATION REQUIRED ---")

    user_input = input(f"\nPlease confirm: {msg} (y/n): ").strip().lower()
    print(f"user input = {user_input}")
    return user_input == 'y'


def test_launch_netflix_and_verify_playing(client, is_hw):
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
        MOCK_ROKU_STATE["player_state"] = ["stop", "open", "play"]

    # --- Act: Fire the request against your FastAPI rest client route ---
    launch_payload = {
        "app_id": "12",
        "content_id": "81556391",  # Example Netflix movie asset ID
        "content_type": "series"
    }

    # 1. Fire the launch sequence
    launch_response = client.post("launch", json=launch_payload)
    if launch_response.status_code == 422:
        logger.error("\nVALIDATION ERROR DETAILS:", launch_response.json())
    assert launch_response.status_code == 200
    assert launch_response.json() == {"message": "App 12 launched successfully"}

    # 2. Fire the state query validation check
    state_response = client.get("/status")
    assert state_response.status_code == 200
    response_data = state_response.json()
    state = response_data[0]
    assert state == "play"

    # Prove that your controller maps the XML response safely into standard fields
    # (Adjust field keys depending on what your route explicitly outputs in main.py)
    assert "Netflix" in str(state_response.json())

    if is_hw:
        assert confirmation("Did the show launch?") is True

    asyncio.sleep(5)

    restart_response = client.post("restart", json={"pause": "false"})
    assert restart_response.status_code == 200
    assert restart_response.json() == {"message": "Restart command sent"}

    if is_hw:
        assert confirmation("Did the show restart?")

