from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import httpx
import uvicorn

from max_roku.roku_controller import RokuController

app = FastAPI(title="Roku Control API")

# Global variable to hold our controller and client
# In a production app, you might use a more robust dependency injection pattern
state = {
    "controller": None,
    "client": None
}


class LaunchRequest(BaseModel):
    app_id: str
    content_id: Optional[str] = None
    content_type: Optional[str] = None


class RestartRequest(BaseModel):
    pause: bool = False


@app.on_event("startup")
async def startup_event():
    # In a real scenario, you'd pass the IP via environment variable or config
    roku_ip = "192.168.2.64"
    state["client"] = httpx.AsyncClient()
    state["controller"] = RokuController(roku_ip, state["client"])
    print(f"Service started. Targeting Roku at {roku_ip}")


@app.on_event("shutdown")
async def shutdown_event():
    await state["client"].aclose()


def get_controller() -> RokuController:
    if state["controller"] is None:
        raise HTTPException(status_code=500, detail="Controller not initialized")
    return state["controller"]


# --- Status Endpoints ---

@app.get("/status")
async def get_status(controller: RokuController = Depends(get_controller)):
    """Returns the current media player state."""
    state_data = await controller.get_media_player_state()
    if not state_data:
        raise HTTPException(status_code=500, detail="Failed to fetch state")
    return state_data


# --- Navigation Endpoints ---

@app.post("/press/{command}")
async def press_command(command: str, controller: RokuController = Depends(get_controller)):
    """Generic endpoint for simple button presses
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
    cmd = command.capitalize()

    if cmd not in controller.CMD_LIST:
        raise HTTPException(status_code=400, detail=f"Command '{command}' not supported")

    await controller.send_command(cmd)
    return {"message": f"Command {command} sent successfully"}


# --- Action Endpoints ---

@app.post("/launch")
async def launch_app(req: LaunchRequest, controller: RokuController = Depends(get_controller)):
    """Launches a specific app."""
    success = await controller.launch_app(req.app_id, req.content_id, req.content_type)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to launch app")
    return {"message": f"App {req.app_id} launched successfully"}


@app.post("/restart")
async def restart_player(req: RestartRequest, controller: RokuController = Depends(get_controller)):
    """Restarts the current media."""
    success = await controller.restart_current(req.pause)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to restart media")
    return {"message": "Restart command sent"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
