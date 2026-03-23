"""Agent FastAPI application.

Exposes HTTP endpoints for dashboard to query printer status,
inject jobs, and send movement/print commands.
Also serves a WebSocket endpoint for real-time status streaming.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from common.models.job import Job
from common.models.printer import PrinterStatus
from agent.printer.backend import PrinterBackend

app = FastAPI(title="PrintFlow Agent", version="0.1.0")

# Set by main.py before app starts
_backend: PrinterBackend | None = None
_printer_name: str = "PrintFlow-Agent"
_printer_type: str = "dtg"


def set_backend(backend: PrinterBackend) -> None:
    """Inject the backend instance (called from main.py)."""
    global _backend
    _backend = backend


def set_printer_info(name: str, printer_type: str) -> None:
    """Set printer identity for /health and /status responses."""
    global _printer_name, _printer_type
    _printer_name = name
    _printer_type = printer_type


def _get_backend() -> PrinterBackend:
    if _backend is None:
        raise HTTPException(status_code=503, detail="Backend not initialized")
    return _backend


# --- Request / Response models ----------------------------------------

class JobRequest(BaseModel):
    """POST /jobs request body."""

    job_id: str
    order_id: str
    prn_path: str
    job_name: str = "print-job"


class CommandRequest(BaseModel):
    """POST /control/{command} request body (optional payload)."""

    payload: dict[str, Any] = {}


# --- Routes -----------------------------------------------------------

@app.get("/health")
def health_check() -> dict[str, str]:
    """Agent liveness probe — includes printer identity for auto-registration."""
    return {
        "status": "ok",
        "service": "printflow-agent",
        "printer_type": _printer_type,
        "printer_name": _printer_name,
        "version": "0.1.0",
    }


@app.get("/status")
async def get_status() -> PrinterStatus:
    """Return current printer status snapshot."""
    backend = _get_backend()
    return await backend.get_status()


@app.post("/jobs")
async def inject_job(req: JobRequest) -> dict[str, Any]:
    """Inject a print job into PrintExp.

    Returns success flag and bytes sent.
    """
    backend = _get_backend()
    ok = await backend.inject_job(req.prn_path, req.job_name)
    if not ok:
        raise HTTPException(status_code=500, detail="Job injection failed")
    return {"success": True, "job_id": req.job_id}


@app.post("/control/{command}")
async def send_control(command: str) -> dict[str, Any]:
    """Send a named movement or print command to the printer.

    Valid commands: move_left, move_right, move_ahead, move_back,
    print_start, pause, cancel, home_x, home_y, clean, flash, etc.
    """
    backend = _get_backend()
    ok = await backend.send_command(command)
    if not ok:
        raise HTTPException(status_code=500, detail=f"Command '{command}' failed")
    return {"success": True, "command": command}


# --- WebSocket real-time status stream --------------------------------

class _ConnectionManager:
    """Track active WebSocket connections."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.remove(ws)

    async def broadcast(self, data: str) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)


_manager = _ConnectionManager()


@app.websocket("/ws")
async def websocket_status(websocket: WebSocket) -> None:
    """WebSocket endpoint — push printer status every 2 seconds."""
    await _manager.connect(websocket)
    backend = _get_backend()

    try:
        while True:
            status = await backend.get_status()
            payload = status.__class__.__name__ + ":" + json.dumps(
                {
                    "type": status.type,
                    "connected": status.connected,
                    "printing": status.printing,
                    "position_x": status.position_x,
                    "position_y": status.position_y,
                    "ink_levels": status.ink_levels,
                    "current_job": status.current_job,
                }
            )
            await _manager.broadcast(payload)
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        _manager.disconnect(websocket)
