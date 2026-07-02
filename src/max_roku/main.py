import asyncio
from http import HTTPStatus
from contextlib import asynccontextmanager
from os import getenv

from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
import httpx
import uvicorn

from max_roku.roku_controller import RokuController, Command
from max_roku.discover import discover_roku_ip
from max_roku.provider import get_provider



@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---

    roku_ip = getenv("ROKU_IP") or await asyncio.to_thread(discover_roku_ip)
    if not roku_ip:
        raise RuntimeError("Could not determine Roku IP (set ROKU_IP or ensure device is discoverable)")

    client = httpx.AsyncClient()
    app.state.client = client
    app.state.controller = RokuController(roku_ip, client)
    print(f"Service started. Targeting Roku at {roku_ip}")

    yield

    # --- Shutdown ---
    if client is not None:
        await client.aclose()


roku_app = FastAPI(title="Roku Control API", lifespan=lifespan)


class LaunchRequest(BaseModel):
    app_id: str
    content_id: Optional[str] = None
    content_type: Optional[str] = None


class RestartRequest(BaseModel):
    pause: bool = False


def get_controller(request: Request) -> RokuController:
    controller: Optional[RokuController] = getattr(request.app.state, "controller", None)
    if controller is None:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Controller not initialized")
    return controller


# --- Status Endpoints ---

@roku_app.get("/status")
async def get_status(controller: RokuController = Depends(get_controller)):
    """Returns the current media player state."""
    state_data = await controller.get_media_player_state()
    if not state_data:
        raise HTTPException(status_code=500, detail="Failed to fetch state")
    return state_data


# --- Navigation Endpoints ---

@roku_app.post("/press/{command}")
async def press_command(command: str, controller: RokuController = Depends(get_controller)):
    """Generic endpoint for a simple button presses
    Navigation & Menus
        Home: Returns to the Roku home screen.
        Back: Returns to the previous screen.
        Select: Selects the currently highlighted item (equivalent to "OK").
        Up / Down / Left / Right: Directional pad navigation.
    Media Playback
        Play: Toggles between play and pause.
        Rev: Rewinds the media.
        Fwd: Fast-forwards the media.
        InstantReplay: Skips back a few seconds (the circular arrow button).
    """

    try:
        cmd = Command(command.capitalize())
        await controller.send_command(cmd)

    except ValueError:
        raise HTTPException(status_code=400, detail=f"Command '{command}' not supported")


    return {"message": f"Command {cmd} sent successfully"}


# --- Action Endpoints ---

@roku_app.post("/launch")
async def launch_app(req: LaunchRequest, controller: RokuController = Depends(get_controller)):
    """Launches a specific app using the provider appropriate for its app_id."""
    provider = get_provider(req.app_id, controller)
    success = await provider.launch(req.content_id, req.content_type)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to launch app")
    return {"message": f"App {req.app_id} launched successfully"}


@roku_app.post("/get-active-app")
async def get_active_app(controller: RokuController = Depends(get_controller)):
    """Launches a specific app using the provider appropriate for its app_id."""
    active_app = await controller.get_active_app()
    if not active_app:
        raise HTTPException(status_code=500, detail="Failed to query active app")
    return active_app

@roku_app.post("/restart")
async def restart_player(req: RestartRequest, controller: RokuController = Depends(get_controller)):
    """Restarts the current media."""
    success = await controller.restart_current(req.pause)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to restart media")
    return {"message": "Restart command sent"}


if __name__ == "__main__":
    uvicorn.run(roku_app, host="0.0.0.0", port=8000)
