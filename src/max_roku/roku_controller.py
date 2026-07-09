from http import HTTPStatus
from typing import Literal, Any, Optional, Tuple, Dict

from loguru import logger

import httpx
import xmltodict
from xml.parsers.expat import ExpatError
import asyncio

from max_roku.exceptions import RokuConnectionError, RokuCommandError, RokuUnexpectedState, RokuParsingError
from max_roku.constants import Command

PAUSE_TIME = 5
MAX_RETRIES = 12

type PlayerState = Literal["stop", "play", "pause", "unknown"]


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
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Command rejected: {e.response.status_code}")
            raise RokuCommandError(f"Roku rejected command '{command}' with status {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"Network error: {e}")
            raise RokuConnectionError("Failed to communicate with Roku device") from e

        logger.info(f"Successfully sent command: {command}")
        return


    async def launch_app(self, app_id, content_id=None, content_type=None):
        """
        Launches a specific application on the Roku via deep-link.
        Returns True if the launch HTTP call succeeded (does NOT guarantee playback).
        """
        url = f"{self.base_url}/launch/{app_id}"

        params = {}
        if content_id:
            params['contentId'] = content_id
        if content_type:
            params['mediaType'] = content_type
        logger.info(f"Post Params={params} URL= {url}")

        try:
            response = await self.client.post(url, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Command rejected: {e.response.status_code}")
            raise RokuCommandError(f"Roku rejected launch for app_id = {app_id}, content_id = {content_id}, "
                                   f"content_type = {content_type} with status {e.response.status_code}"
                  ) from e
        except httpx.RequestError as e:
            logger.error(f"Network error: {e}")
            raise RokuConnectionError("Failed to communicate with Roku device") from e

        logger.info(
            f"Successfully launched: app_id = {app_id}, content_id = {content_id} content_type = {content_type} ")
        return

    # async def restart_current(self, pause: bool):
    #     """
    #     Resets the current playing media to the start, and either pauses or plays.
    #     The media player state must = 'pause' or 'play'.
    #     """
    #     # Ensure player has responded to any previous request
    #     await asyncio.sleep(PAUSE_TIME)
    #     state, _ = await self.get_media_player_state()
    #     logger.info(f"Restart: Initial State ={state} Plugin_app={self.plugin_app['@id']}")
    #
    #     if state in ['play', 'pause'] and self.plugin_app:
    #         provider = get_provider(self.plugin_app["@id"], self)
    #         await provider.restart(pause)
    #     else:
    #         raise RokuUnexpectedState(
    #             f"Restart requested but Rocku Media Player  not in 'play' or 'pause' state: {state}"
    #         )
    #     return


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
            logger.info(f"press_until_playing: state={state}")
        return state == "play"


    async def get_active_app(self):
        """
        Queries the Roku device to find out which app is currently running.
        Returns a dict that maps the raw XML response text.
        If an app is active:
            <active-app>
                <app id="<id>" type="appl" version="<version>"<name></app>
            </active-app>
        mapped to:
            {"active_app": {"@id":<id>, "@type": "appl", "@version": "<version>", "#text":"<name>"}}
        If no app is active:
        <active-app>
            <app>Roku</app>
        </active-app>
                mapped to:
            {"active_app": {"#text":"Roku"}}
        """
        url = f"{self.base_url}/query/active-app"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RokuCommandError(f"Roku rejected '/query/active-app' with status {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise RokuConnectionError("Failed to communicate with Roku device") from e

        try:
            active_app = xmltodict.parse(response.text)["active-app"].get("app")
        except ExpatError as e:
            raise RokuParsingError(f"Failed to parse XML response {response.text}") from e

        logger.info(f"Successfully retrieved active app = {active_app}.")
        return active_app

    async def get_media_player_state(self) -> Tuple[Optional[PlayerState], Optional[Dict[str, Any]]]:
        """
        Queries the Roku device for the current playback state of the media player.
        Returns response a dictionary containing the XML response.
        """
        url = f"{self.base_url}/query/media-player"

        # 1. Step One: Separate the Network Operation
        try:
            response = await self.client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == HTTPStatus.NOT_FOUND:
                raise RokuUnexpectedState(
                    "Media player query endpoint is not supported in the current device context."
                ) from e
            raise RokuCommandError(f"Roku returned a bad status code: {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise RokuConnectionError(f"Failed to communicate with Roku device") from e

        # 2. Step Two: Separate the XML Parsing
        try:
            raw_state = xmltodict.parse(response.text)
        except ExpatError as e:
            raise RokuParsingError(f"Malformed XML payload returned from Roku") from e

        # 3. Step Three: Map the data safely using sequential guards
        try:
            player_data = raw_state["player"]

            # Guard against blank whitespace or missing positions safely
            position = player_data.get("position")
            if position and position.split():
                self.position = int(position.split()[0])

            self.plugin_app = player_data.get("plugin")
            state = player_data.get("@state", "unknown")

        except (KeyError, IndexError, ValueError) as e:
            raise RokuParsingError(f"Roku API schema mismatch or unexpected values") from e

        # 4. Final step: Update State Machine representation
        if state in ("stop", "close", "none"):
            self._state = "stop"
        elif state in ("play", "buffer", "buffering"):
            self._state = "play"
        elif state == "pause":
            self._state = "pause"
        else:
            self._state = "unknown"
            logger.error(f"Unknown State received: {state}")

        logger.info(f"Successfully got state: {self._state}")
        return self._state, raw_state
