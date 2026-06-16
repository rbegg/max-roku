import requests
from time import sleep
import xmltodict

PAUSE_TIME = 5
MAX_RETRIES = 12

class RokuController:
    """
    Class to call the Roku ECP commands
    Navigation & Menus
        Home: Returns to the Roku home screen.
        Back: Returns to the previous screen.
        Select: Selects the currently highlighted item (equivalent to "OK").
        Up / Down / Left / Right: Directional pad navigation.
        Info: Simulates pressing the asterisk (*) button for options. **not implemented**
        Enter: Simulates the enter key.**not implemented**
        Backspace: Deletes the last character in a text field.**not implemented**
        Search: Opens the search menu. **not implemented**
    Media Playback
        Play: Toggles between play and pause.
        Rev: Rewinds the media.
        Fwd: Fast-forwards the media.
        InstantReplay: Skips back a few seconds (the circular arrow button).
        Pause: Explicitly pauses the media (if the app supports it).**not implemented**
    """
    CMD_LIST = ['Home', 'Back', 'Select', 'Up', 'Down', 'Left', 'Right', 'Play', 'Rev', 'Fwd', 'InstantReplay']
    def __init__(self, ip_address):
        """
        Initialize the controller with the Roku device's IP address.
        """
        # noinspection HttpUrlsUsage
        self.base_url = f"http://{ip_address}:8060"
        self.media_player_state = {}
        self.state = "stop"
        self.position = None # in milliseconds if known
        ##self.state

    def _send_command(self, command):
        """
        Internal method to send the POST request to the ECP endpoint.
        """
        url = f"{self.base_url}/keypress/{command}"
        try:
            response = requests.post(url)
            if response.status_code == 200:
                print(f"Successfully sent command: {command}")
            else:
                print(f"Failed to send command. Status code: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"Error: Could not connect to Roku at {self.base_url}. Is the IP correct?")
        except Exception as e:
            print(f"An error occurred: {e}")

    def press_home(self):
        """Home: Returns to the Roku home screen."""
        self._send_command("Home")

    def press_back(self):
        """Back: Returns to the previous screen."""
        self._send_command("Back")

    def press_select(self):
        """Select: Selects the currently highlighted item (equivalent to "OK")."""
        self._send_command("Select")

    def press_left(self):
        """Left: Directional pad navigation."""
        self._send_command("Left")

    def press_right(self):
        """Right: Directional pad navigation."""
        self._send_command("Right")

    def press_up(self):
        """Up: Directional pad navigation."""
        self._send_command("Up")

    def press_down(self):
        """Down: Directional pad navigation."""
        self._send_command("Down")

    def press_play_pause(self):
        """Play: Toggles between play and pause."""
        self._send_command("Play")

    def press_rev(self):
        """Rev: Rewinds the media"""
        self._send_command("Rev")

    def press_fwd(self):
        """Fwd: Fast-forwards the media"""
        self._send_command("Fwd")

    def press_instant_replay(self):
        self._send_command("InstantReplay")

    def press_pause(self):
        self._send_command("Pause")

    def launch_app(self, app_id, content_id=None, content_type=None) -> bool:
        """
        Launches a specific application on the Roku.
        Supports deep linking via content_id and content_type.
        """
        url = f"{self.base_url}/launch/{app_id}"

        # Prepare query parameters for deep linking
        params = {}
        if content_id:
            params['contentID'] = content_id
        if content_type:
            params['mediaType'] = content_type

        try:
            # Using 'params' automatically appends ?contentId=...&contentType=... to the URL
            response = requests.post(url, params=params)
            print(f"POST: {response.url}")
            if response.status_code == 200:
                print(f"Successfully sent launch command for: {app_id} (Deep link: {bool(content_id)})")
                sleep(PAUSE_TIME*2)
                self.get_media_player_state()
                print(f"1-State: {self.state}")
                retry = 0
                if not content_id:
                    return False

                # Multiple Selects to accept profile and another to start playing may be required
                while self.state != "play" and retry < MAX_RETRIES:
                    retry +=1
                    sleep(PAUSE_TIME)
                    self.press_select()
                    sleep(PAUSE_TIME)
                    self.get_media_player_state()
                    print(f"2-State: {self.state}")

                if self.state == "play":
                    return True
                else:
                    print(f"Not in play state!!  State = {self.state}")
                    return False
            else:
                print(f"Unexpected Response Code = {response.status_code}")
                return False
        except Exception as e:
            print(f"An error occurred while launching {app_id}: {e}")

        return False

    def restart_current(self, pause: bool):
        """
        Resets the current playing media to the start, and either pauses or plays.
        The media player state must = 'pause' or 'play'.
        :param pause: If True, the media will be reset to the start and then paused.
                      If False, the media will replay from the start.
        :return: True if successful, False if the meda player is in an unexpected state.
        """
        # Ensure player has responded to any previous request
        sleep(PAUSE_TIME)
        self.get_media_player_state()
        print(f"Restart: Initial State ={self.state}")
        if self.state in ['play', 'pause']:
            if not self.position:
                print(f"Expected position value")
                return False
            # if less than 30 seconds of media has played, back will not yield a 'restart from beginning' option
            if self.position < 35000:
                print(f"Need to fast fwd ")
                self.press_fwd()
                sleep(PAUSE_TIME)
                self.press_play_pause()
                sleep(PAUSE_TIME)

            self.press_back()
            sleep(PAUSE_TIME)
            self.press_down()
            sleep(1)
            self.press_select()
            sleep(1)
            if pause:
                print("Pausing")
                sleep(PAUSE_TIME)
                self.press_play_pause()
                sleep(PAUSE_TIME)
            self.get_media_player_state()
            print(f"Restart: Final State = {self.state}")
            return True
        return False

    def get_active_app(self):
        """
        Queries the Roku device to find out which app is currently running.
        Returns the raw XML response text.
        """
        url = f"{self.base_url}/query/active-app"
        try:
            # Note: Query endpoints require GET requests, unlike keypresses which use POST
            response = requests.get(url)
            if response.status_code == 200:
                print("Successfully retrieved active app.")
                return response.text
            else:
                print(f"Failed to get active app. Status code: {response.status_code}")
                return None
        except Exception as e:
            print(f"An error occurred while querying active app: {e}")
            return None

    def get_media_player_state(self) -> dict | None:
        """
        Queries the Roku device for the current playback state of the media player.
        Returns the raw XML response text.
        """
        url = f"{self.base_url}/query/media-player"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                print("Successfully retrieved media player state.")
                self.media_player_state = xmltodict.parse(response.text)
                position = self.media_player_state["player"].get("position", None)
                if position:
                    self.position = int(position.split()[0])
                state = self.media_player_state["player"].get("@state", "")
                if state in ("stop", "close", "none"):
                    self.state = "stop"
                elif state in ("play", "buffer", "buffering"):
                    self.state = "play"
                elif state == "pause":
                    self.state = "pause"
                else:
                    print(f"Unknown State: {state}")

                return self.media_player_state
            else:
                print(f"Failed to get media player state. Status code: {response.status_code}")
                return None
        except Exception as e:
            print(f"An error occurred while querying media player state: {e}")
            return None
