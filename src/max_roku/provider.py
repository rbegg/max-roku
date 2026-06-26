from abc import ABC, abstractmethod
from time import sleep
import asyncio

PAUSE_TIME = 5

class Provider(ABC):
    """
    Base class for a streaming provider. Each provider knows its Roku
    app id and how to drive the controller through its launch quirks.
    """

    # Roku channel/app id, e.g. "12" for Netflix, "291097" for Disney+
    app_id: str

    def __init__(self, controller, app_id: str | None = None):
        self.controller = controller
        if app_id is not None:
            self.app_id = app_id

    @abstractmethod
    async def launch(self, content_id=None, content_type=None) -> bool:
        """Launch this provider and reach a playing state."""
        ...

    @abstractmethod
    async def restart(self, pause: bool = False) -> bool:
        """Restart the currently playing content from the beginning."""
        ...


class GenericProvider(Provider):
    """
    Default behavior: deep-link launch, then press Select until playing.
    Works for most apps that autoplay on deep-link.
    """

    def __init__(self, controller, app_id: str| None = None):
        super().__init__(controller, app_id)

    async def launch(self, content_id=None, content_type=None) -> bool:
        launched = await self.controller.launch_app(
            self.app_id, content_id, content_type
        )
        if not launched or not content_id:
            return launched
        return await self.controller.press_until_playing()

    async def restart(self, pause: bool = False) -> bool:
        """
        Generic restart is not supported, requires provider details
        """
        return False

    async def pause(self) -> str:
        await self.controller.get_media_player_state()
        print(f"Pause: Initial State = {self.controller.state}")
        if self.controller.state == "play":
            print("Pausing")
            sleep(PAUSE_TIME)
            await self.controller.send_command('Play')
            sleep(PAUSE_TIME)
            await self.controller.get_media_player_state()
        print(f"Pause: Final State = {self.controller.state}")
        return self.controller.state



class NetflixProvider(GenericProvider):
    """
    Netflix needs an explicit extra Play press after the deep link
    resolves, in addition to confirming the profile.
    """

    app_id: str = "12"

    async def launch(self, content_id=None, content_type=None) -> bool:
        launched = await self.controller.launch_app(
            self.app_id, content_id, content_type
        )
        if not launched:
            return False

        # Netflix-specific: confirm profile, then explicitly start playback
        playing = await self.controller.press_until_playing()
        if not playing:
            return False

        return True

    async def restart(self, pause: bool = False) -> bool:
        """
        Resets the current playing media to the start, and either pauses or plays.
        The media player state must = 'pause' or 'play'.
        :param pause: If True, the media will be reset to the start and then paused.
                      If False, the media will replay from the start.
        :return: True if successful, False if the meda player is in an unexpected state.
        """
        # Ensure player has responded to any previous request
        # await asyncio.sleep(PAUSE_TIME)
        await self.controller.get_media_player_state()
        print(f"Restart: Pause={pause} Initial State ={self.controller.state}")
        if self.controller.state in ['play', 'pause']:
            if not self.controller.position:
                print(f"Expected position value")
                return False
            # if less than 30 seconds of media has played, back will not yield a 'restart from beginning' option
            if self.controller.position < 35000:
                print(f"Need to fast fwd ")
                await self.controller.send_command('Fwd')
                await asyncio.sleep(PAUSE_TIME)
                await self.controller.send_command('Play')
                await asyncio.sleep(PAUSE_TIME)

            await self.controller.send_command('Back')
            await asyncio.sleep(PAUSE_TIME)
            await self.controller.send_command('Down')
            await asyncio.sleep(1)
            await self.controller.send_command('Select')
            await asyncio.sleep(1)
            if pause:
                state = await self.pause()
            else:
                await self.controller.get_media_player_state()
                state = self.controller.state

            print(f"Restart: Final State = {state}")
            return True
        return False


class ZinniaProvider(GenericProvider):
    """
    Zinnia
      - Launch: uses generic
      - Restart: requires right/select
    """

    app_id: str = "674313"

    async def restart(self, pause: bool = False) -> bool:
        await self.controller.get_media_player_state()
        print(f"Restart: Initial State ={self.controller.state}")
        if not self.controller.position:
            print(f"Expected position value")
            return False
        # if less than 5 seconds of media has played, back will not yield a 'restart from beginning' option
        #
        if self.controller.position < 5000:
            return True

        #
        await self.controller.send_command('Back')
        await asyncio.sleep(PAUSE_TIME)
        await self.controller.send_command('Right')
        await asyncio.sleep(PAUSE_TIME)
        await self.controller.send_command('Select')
        await asyncio.sleep(PAUSE_TIME)
        if pause:
            state = await self.pause()
        else:
            state = await self.controller.get_media_player_state()
        print(f"Restart: Final State = {state}")

        return True


# Providers that have special launch behavior, keyed by Roku app_id
_SPECIAL_PROVIDERS = {
    NetflixProvider.app_id: NetflixProvider,
    ZinniaProvider.app_id: ZinniaProvider,
}


def get_provider(app_id: str, controller) -> Provider:
    """
    Resolve the correct provider for a given app_id.
    Falls back to GenericProvider for apps without special handling.
    """
    cls = _SPECIAL_PROVIDERS.get(app_id)
    if cls is not None:
        return cls(controller, app_id)
    return GenericProvider(controller, app_id)