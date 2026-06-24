import httpx
from time import sleep
import xmltodict
import asyncio

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
    def __init__(self, ip_address, client: httpx.AsyncClient):
        """
        Initialize the controller with the Roku device's IP address.
        """
        # noinspection HttpUrlsUsage
        self.base_url = f"http://{ip_address}:8060"
        self.client = client
        self.media_player_state = {}
        self.state = "stop"
        self.position = None # in milliseconds if known

    async def send_command(self, command):
        """
        Internal method to send the POST request to the ECP endpoint.
        """
        url = f"{self.base_url}/keypress/{command}"
        try:
            response = await self.client.post(url)
            if response.status_code == 200:
                print(f"Successfully sent command: {command}")
            else:
                print(f"Failed to send command. Status code: {response.status_code}")
        #except requests.exceptions.ConnectionError:
            #print(f"Error: Could not connect to Roku at {self.base_url}. Is the IP correct?")
        except Exception as e:
            print(f"An error occurred: {e}")

    async def launch_app(self, app_id, content_id=None, content_type=None) -> bool:
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
            response = await self.client.post(url, params=params)
            print(f"POST: {response.url}")
            if response.status_code == 200:
                print(f"Successfully sent launch command for: {app_id} (Deep link: {bool(content_id)})")
                await asyncio.sleep(PAUSE_TIME*2)
                await self.get_media_player_state()
                print(f"1-State: {self.state}")
                retry = 0
                if not content_id:
                    return False

                # Multiple Selects to accept profile and another to start playing may be required
                while self.state != "play" and retry < MAX_RETRIES:
                    retry +=1
                    await asyncio.sleep(PAUSE_TIME)
                    await self.send_command('Select')
                    await asyncio.sleep(PAUSE_TIME)
                    await self.get_media_player_state()
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

    async def restart_current(self, pause: bool):
        """
        Resets the current playing media to the start, and either pauses or plays.
        The media player state must = 'pause' or 'play'.
        :param pause: If True, the media will be reset to the start and then paused.
                      If False, the media will replay from the start.
        :return: True if successful, False if the meda player is in an unexpected state.
        """
        # Ensure player has responded to any previous request
        await asyncio.sleep(PAUSE_TIME)
        await self.get_media_player_state()
        print(f"Restart: Initial State ={self.state}")
        if self.state in ['play', 'pause']:
            if not self.position:
                print(f"Expected position value")
                return False
            # if less than 30 seconds of media has played, back will not yield a 'restart from beginning' option
            if self.position < 35000:
                print(f"Need to fast fwd ")
                await self.send_command('Fwd')
                await asyncio.sleep(PAUSE_TIME)
                await self.send_command('Play')
                await asyncio.sleep(PAUSE_TIME)

            await self.send_command('Back')
            await asyncio.sleep(PAUSE_TIME)
            await self.send_command('Down')
            await asyncio.sleep(1)
            await self.send_command('Select')
            await asyncio.sleep(1)
            if pause:
                print("Pausing")
                sleep(PAUSE_TIME)
                await self.send_command('Play')
                sleep(PAUSE_TIME)
            await self.get_media_player_state()
            print(f"Restart: Final State = {self.state}")
            return True
        return False

    async def get_active_app(self):
        """
        Queries the Roku device to find out which app is currently running.
        Returns the raw XML response text.
        """
        url = f"{self.base_url}/query/active-app"
        try:
            # Note: Query endpoints require GET requests, unlike keypresses which use POST
            response = await self.client.get(url)
            if response.status_code == 200:
                print("Successfully retrieved active app.")
                return response.text
            else:
                print(f"Failed to get active app. Status code: {response.status_code}")
                return None
        except Exception as e:
            print(f"An error occurred while querying active app: {e}")
            return None

    async def get_media_player_state(self) -> dict | None:
        """
        Queries the Roku device for the current playback state of the media player.
        Returns the raw XML response text.
        """
        url = f"{self.base_url}/query/media-player"
        try:
            response = await self.client.get(url)
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
