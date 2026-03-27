"""Agent FastAPI application.

Exposes HTTP endpoints for dashboard to query printer status,
inject jobs, send movement/print commands, and browse local files.
Also serves a WebSocket endpoint for real-time status streaming.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from starlette.middleware.cors import CORSMiddleware

from common.models.job import Job
from common.models.printer import PrinterStatus
from agent.printer.backend import PrinterBackend
from agent.printer.uv_print_mode_service import UVPrintModeService
from agent.reports import router as reports_router

app = FastAPI(title="PrintFlow Agent", version="0.1.0")
app.include_router(reports_router)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Set by main.py before app starts
_backend: PrinterBackend | None = None
_printer_name: str = "PrintFlow-Agent"
_printer_type: str = "dtg"
_print_mode_service: UVPrintModeService | None = None


def set_backend(backend: PrinterBackend) -> None:
    """Inject the backend instance (called from main.py)."""
    global _backend
    _backend = backend


def set_printer_info(name: str, printer_type: str) -> None:
    """Set printer identity for /health and /status responses."""
    global _printer_name, _printer_type
    _printer_name = name
    _printer_type = printer_type


def set_print_mode_service(service: UVPrintModeService) -> None:
    """Inject the UV print mode service (called from main.py for UV agents)."""
    global _print_mode_service
    _print_mode_service = service


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
    workstation: int | None = None  # 0=WS:0, 1=WS:1, None=auto (DTG MULTIWS)


class CommandRequest(BaseModel):
    """POST /control/{command} request body (optional payload)."""

    payload: dict[str, Any] = {}


class PrintModeRequest(BaseModel):
    """POST /print-mode request body."""

    preset: str


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
    ok = await backend.inject_job(req.prn_path, req.job_name, workstation=req.workstation)
    if not ok:
        raise HTTPException(status_code=500, detail="Job injection failed")
    return {"success": True, "job_id": req.job_id}


@app.get("/ws-status")
async def get_ws_status() -> dict[str, Any]:
    """Return MULTIWS workstation busy state (DTG dual-platen only)."""
    backend = _get_backend()
    status = await backend.get_status()
    return {
        "active_ws": status.active_ws,
        "ws0_busy": status.ws0_busy,
        "ws1_busy": status.ws1_busy,
    }


@app.get("/files")
async def list_files(
    dir: str = Query(default="", description="Directory to list"),
) -> list[dict[str, Any]]:
    """List .prn/.prt files and subdirectories for file browser.

    If dir is empty, returns common starting locations.
    """
    PRN_EXTS = {".prn", ".prt"}

    if not dir:
        # Return common starting points
        home = os.path.expanduser("~")
        roots = [
            {"name": "Desktop", "path": os.path.join(home, "Desktop"), "type": "dir"},
            {"name": "Documents", "path": os.path.join(home, "Documents"), "type": "dir"},
            {"name": "Downloads", "path": os.path.join(home, "Downloads"), "type": "dir"},
        ]
        # Add drive letters
        for letter in "CDEFG":
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                roots.append({"name": drive, "path": drive, "type": "dir"})
        return [r for r in roots if os.path.exists(r["path"])]

    target = Path(dir)
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail=f"Directory not found: {dir}")

    items = []
    # Parent directory
    parent = str(target.parent)
    if parent != str(target):
        items.append({"name": "..", "path": parent, "type": "dir"})

    try:
        for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                items.append({"name": entry.name, "path": str(entry), "type": "dir"})
            elif entry.suffix.lower() in PRN_EXTS:
                size_kb = entry.stat().st_size // 1024
                items.append({
                    "name": entry.name,
                    "path": str(entry),
                    "type": "file",
                    "size": f"{size_kb} KB",
                })
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return items


@app.post("/files/browse")
async def browse_file() -> dict[str, Any]:
    """Open native Windows file picker dialog via Win32 API."""
    import ctypes
    import ctypes.wintypes as wt
    import threading

    result = {"path": None}

    def _open_dialog():
        try:
            comdlg32 = ctypes.windll.comdlg32
            # OPENFILENAMEW structure
            class OPENFILENAMEW(ctypes.Structure):
                _fields_ = [
                    ("lStructSize", wt.DWORD),
                    ("hwndOwner", wt.HWND),
                    ("hInstance", wt.HINSTANCE),
                    ("lpstrFilter", wt.LPCWSTR),
                    ("lpstrCustomFilter", wt.LPWSTR),
                    ("nMaxCustFilter", wt.DWORD),
                    ("nFilterIndex", wt.DWORD),
                    ("lpstrFile", wt.LPWSTR),
                    ("nMaxFile", wt.DWORD),
                    ("lpstrFileTitle", wt.LPWSTR),
                    ("nMaxFileTitle", wt.DWORD),
                    ("lpstrInitialDir", wt.LPCWSTR),
                    ("lpstrTitle", wt.LPCWSTR),
                    ("Flags", wt.DWORD),
                    ("nFileOffset", wt.WORD),
                    ("nFileExtension", wt.WORD),
                    ("lpstrDefExt", wt.LPCWSTR),
                    ("lCustData", ctypes.POINTER(ctypes.c_long)),
                    ("lpfnHook", ctypes.c_void_p),
                    ("lpTemplateName", wt.LPCWSTR),
                    ("pvReserved", ctypes.c_void_p),
                    ("dwReserved", wt.DWORD),
                    ("FlagsEx", wt.DWORD),
                ]

            buf = ctypes.create_unicode_buffer(512)
            ofn = OPENFILENAMEW()
            ofn.lStructSize = ctypes.sizeof(OPENFILENAMEW)
            ofn.hwndOwner = None
            ofn.lpstrFilter = "PRN Files (*.prn;*.prt)\0*.prn;*.prt\0All Files (*.*)\0*.*\0\0"
            ofn.lpstrFile = ctypes.cast(buf, wt.LPWSTR)
            ofn.nMaxFile = 512
            ofn.lpstrTitle = "Select PRN File"
            ofn.Flags = 0x00080000 | 0x00001000 | 0x00000800  # EXPLORER | FILEMUSTEXIST | PATHMUSTEXIST

            if comdlg32.GetOpenFileNameW(ctypes.byref(ofn)):
                result["path"] = buf.value
        except Exception as e:
            pass

    t = threading.Thread(target=_open_dialog)
    t.start()
    t.join(timeout=120)

    if not result["path"]:
        raise HTTPException(status_code=204, detail="No file selected")
    return {"path": result["path"]}


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


# --- Print Mode (UV only) ---------------------------------------------

@app.get("/print-mode")
async def get_print_mode() -> dict[str, Any]:
    """Return current print mode and available presets (UV printers only)."""
    if _print_mode_service is None:
        raise HTTPException(status_code=404, detail="Print modes only available for UV printers")
    current = _print_mode_service.get_current_mode()
    presets = _print_mode_service.get_presets()
    return {"current": current, "presets": presets}


@app.post("/print-mode")
async def set_print_mode(req: PrintModeRequest) -> dict[str, Any]:
    """Apply a print mode preset (UV printers only)."""
    if _print_mode_service is None:
        raise HTTPException(status_code=404, detail="Print modes only available for UV printers")

    result = await asyncio.to_thread(_print_mode_service.apply_preset, req.preset)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed"))
    return result


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
                    "active_ws": status.active_ws,
                    "ws0_busy": status.ws0_busy,
                    "ws1_busy": status.ws1_busy,
                }
            )
            await _manager.broadcast(payload)
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        _manager.disconnect(websocket)
