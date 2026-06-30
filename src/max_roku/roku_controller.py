from http import HTTPStatus
from typing import Literal, Any, Optional, Tuple, Dict
from enum import StrEnum

import httpx
import xmltodict
import asyncio

from max_roku.provider import get_provider

PAUSE_TIME = 5
MAX_RETRIES = 12

type PlayerState = Literal["stop", "play", "pause", "unknown"]

class Command(StrEnum):
    HOME = "Home"
    BACK = "Back"
    SELECT = "Select"
    UP = "Up"
    DOWN = "Down"
    LEFT = "Left"
    RIGHT = "Right"
    PLAY = "Play"
    REV = "Rev"
    FWD = "Fwd"

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
        self._state : PlayerState = "stop"
        self.position = None # in milliseconds if known
        self.plugin_app = None

    def get_state(self) -> PlayerState:
        return self._state

    async def send_command(self, command: Command):
        """
        Internal method to send the POST request to the ECP endpoint.
        """
        url = f"{self.base_url}/keypress/{command}"
        try:
            response = await self.client.post(url)
            if response.status_code == HTTPStatus.OK:
                print(f"Successfully sent command: {command}")
            else:
                print(f"Failed to send command. Status code: {response.status_code}")
        #except requests.exceptions.ConnectionError:
            #print(f"Error: Could not connect to Roku at {self.base_url}. Is the IP correct?")
        except Exception as e:
            print(f"An error occurred: {e}")

    async def launch_app(self, app_id, content_id=None, content_type=None) -> bool:
        """
        Launches a specific application on the Roku via deep-link.
        Returns True if the launch HTTP call succeeded (does NOT guarantee playback).
        """
        url = f"{self.base_url}/launch/{app_id}"

        params = {}
        if content_id:
            params['contentID'] = content_id
        if content_type:
            params['mediaType'] = content_type

        try:
            response = await self.client.post(url, params=params)
            print(f"POST: {response.url}")
            if response.status_code == HTTPStatus.OK:
                print(f"Successfully launched: {app_id} (Deep link: {bool(content_id)})")
                await asyncio.sleep(PAUSE_TIME * 2)
                await self.get_media_player_state()
                return True
            print(f"Unexpected Response Code = {response.status_code}")
            return False
        except Exception as e:
            print(f"An error occurred while launching {app_id}: {e}")
            return False

    async def restart_current(self, pause: bool) -> bool:
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
        print(f"Restart: Initial State ={self._state} Plugin_app={self.plugin_app['@id']}")

        if self._state in ['play', 'pause'] and self.plugin_app:
            provider = get_provider(self.plugin_app["@id"], self)
            return await provider.restart(pause)

        return False

    async def press_until_playing(self, max_retries: int = MAX_RETRIES) -> bool:
        """
        Repeatedly presses 'Select' until the media player reports 'play'.
        Useful for apps that require confirming a profile or pressing play.
        """
        retry = 0
        state, _ = await self.get_media_player_state()
        while state != "play" and retry < max_retries:
            retry += 1
            await asyncio.sleep(PAUSE_TIME)
            await self.send_command(Command.SELECT)
            await asyncio.sleep(PAUSE_TIME)
            state, _ = await self.get_media_player_state()
            print(f"press_until_playing: state={state}")
        return state == "play"


    async def get_active_app(self):
        """
        Queries the Roku device to find out which app is currently running.
        Returns the raw XML response text.
        """
        url = f"{self.base_url}/query/active-app"
        try:
            # Note: Query endpoints require GET requests, unlike keypresses which use POST
            response = await self.client.get(url)
            if response.status_code == HTTPStatus.OK:
                print("Successfully retrieved active app.")
                return response.text
            else:
                print(f"Failed to get active app. Status code: {response.status_code}")
                return None
        except Exception as e:
            print(f"An error occurred while querying active app: {e}")
            return None

    async def get_media_player_state(self) -> Tuple[Optional[PlayerState], Optional[Dict[str, Any]]]:
        """
        Queries the Roku device for the current playback state of the media player.
        Returns response a dictionary containing the XML response.
        """
        url = f"{self.base_url}/query/media-player"
        try:
            response = await self.client.get(url)
            if response.status_code == HTTPStatus.OK:
                print("Successfully retrieved media player state.")
                self.media_player_state = xmltodict.parse(response.text)
                position = self.media_player_state["player"].get("position", None)
                if position:
                    self.position = int(position.split()[0])
                self.plugin_app = self.media_player_state["player"].get("plugin", None)
                state = self.media_player_state["player"].get("@state", "")
                if state in ("stop", "close", "none"):
                    self._state = "stop"
                elif state in ("play", "buffer", "buffering"):
                    self._state = "play"
                elif state == "pause":
                    self._state = "pause"
                else:
                    self._state = "unknown"
                    print(f"Unknown State: {state}")

                return self._state, self.media_player_state
            else:
                print(f"Failed to get media player state. Status code: {response.status_code}")
                return None, None
        except Exception as e:
            print(f"An error occurred while querying media player state: {e}")
            return None, None
