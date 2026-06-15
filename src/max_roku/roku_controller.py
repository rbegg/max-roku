import requests
from time import sleep
import xmltodict


class RokuController:
    def __init__(self, ip_address):
        """
        Initialize the controller with the Roku device's IP address.
        """
        self.base_url = f"http://{ip_address}:8060"
        self.media_player_state = {}
        self.state = "stop"
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
        self._send_command("home")

    def press_back(self):
        self._send_command("back")

    def press_select(self):
        self._send_command("select")

    def press_left(self):
        self._send_command("left")

    def press_right(self):
        self._send_command("right")

    def press_up(self):
        self._send_command("up")

    def press_down(self):
        self._send_command("down")

    def press_play_pause(self):
        self._send_command("play")

    def launch_app(self, app_id, content_id=None, content_type=None):
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
                sleep(5)
                self.get_media_player_state()
                if self.state != "play":
                    self.press_play_pause()
                    sleep(5)
                    self.get_media_player_state()
                    if self.state != "play":
                        print(f"Not in play state!!  State = {self.state}")
            else:
                print(f"Failed to launch {app_id}. Status code: {response.status_code}")
        except Exception as e:
            print(f"An error occurred while launching {app_id}: {e}")

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
