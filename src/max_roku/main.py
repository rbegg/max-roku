import asyncio
from http import HTTPStatus
from contextlib import asynccontextmanager
from os import getenv
from loguru import logger

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import httpx
import uvicorn

from max_roku.exceptions import RokuConnectionError, RokuCommandError, RokuUnexpectedState, RokuParsingError
from max_roku.roku_controller import RokuController
from max_roku.discover import discover_roku_ip
from max_roku.provider import get_provider, Provider
from max_roku.constants import Command



@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---

    roku_ip = getenv("ROKU_IP") or await asyncio.to_thread(discover_roku_ip)
    if not roku_ip:
        raise RuntimeError("Could not determine Roku IP (set ROKU_IP or ensure device is discoverable)")

    client = httpx.AsyncClient()
    app.state.client = client
    app.state.controller = RokuController(roku_ip, client)
    init_msg = f"Service started. Targeting Roku at {roku_ip}"
    print(init_msg)
    logger.info(init_msg)

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


# Inside main.py
async def get_current_provider(
        request: Request,
        controller: RokuController = Depends(get_controller)
) -> Provider:
    """
    Unified FastAPI dependency that dynamically resolves the correct provider
    regardless of whether the endpoint is a GET or a POST request.
    """
    app_id = None
    # Case A: If it's a POST with a body payload (like 'launch'), it may have an app_id
    if request.method == "POST":
        body = await request.json()
        app_id = body.get("app_id")


    if not app_id:
        active_app = await controller.get_active_app()
        app_id = active_app.get("@id") or "roku"


    return get_provider(app_id, controller)


# --- Exception Handlers ---

@roku_app.exception_handler(RokuConnectionError)
async def roku_connection_exception_handler(request: Request, exc: RokuConnectionError):
    return JSONResponse(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        content={
            "error": "DeviceUnavailable",
            "detail": str(exc),
            "path": request.url.path,
            "method": request.method
        }
    )

@roku_app.exception_handler(RokuCommandError)
async def roku_command_exception_handler(request: Request, exc: RokuCommandError):
    return JSONResponse(
        status_code=HTTPStatus.BAD_REQUEST,
        content={
            "error": "CommandRejected",
            "detail": str(exc),
            "path": request.url.path,
            "method": request.method
        }
    )

@roku_app.exception_handler(RokuUnexpectedState)
async def roku_unexpected_state_handler(request: Request, exc: RokuUnexpectedState):
    return JSONResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        content={
            "error": "UnexpectedDeviceState",
            "detail": str(exc),
            "path": request.url.path,
            "method": request.method
        }
    )

@roku_app.exception_handler(RokuParsingError)
async def roku_parsing_exception_handler(request: Request, exc: RokuParsingError):
    logger.error(f"Data parsing failed for {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=HTTPStatus.BAD_GATEWAY,
        content={
            "error": "DeviceResponseMalformed",
            "detail": str(exc),
            "path": request.url.path,
            "method": request.method
        }
    )

# --- Status Endpoints ---

@roku_app.get("/get-state")
async def get_state(controller: RokuController = Depends(get_controller)):
    """Returns the current media player state."""
    state_data = await controller.get_media_player_state()
    if not state_data:
        raise HTTPException(status_code=500, detail="Failed to fetch state")
    return state_data


# --- Navigation Endpoints ---

@roku_app.post("/press/{command}")
async def press_command(command: Command, controller: RokuController = Depends(get_controller)):
    """
    Sends a keypress command to Roku
    Note: FastAPI automatically validates that {command} matches a value in the Command StrEnum.

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

    await controller.send_command(command)
    return {"message": f"Command {command} sent successfully"}


# --- Action Endpoints ---

@roku_app.post("/launch")
async def launch_app(req: LaunchRequest, provider: Provider = Depends(get_current_provider)):
    """Launches a specific app and play content using the provider appropriate for its app_id."""
    await provider.launch(req.content_id, req.content_type)
    return {"message": f"Launch successful: req = {req} "}


@roku_app.get("/get-active-app")
async def get_active_app(controller: RokuController = Depends(get_controller)):
    """Returns the active app."""
    active_app = await controller.get_active_app()
    return active_app

@roku_app.post("/restart")
async def restart_player(req: RestartRequest, provider: Provider = Depends(get_current_provider)):
    """Restarts the current media."""
    await provider.restart(req.pause)
    return {"message": "Restart command sent"}


if __name__ == "__main__":
    uvicorn.run(roku_app, host="0.0.0.0", port=8000)
