"""Printers API — CRUD registry, live status, control, and HTMX HTML partials."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from dashboard.db.database import get_db
from dashboard.db.models import Printer
from dashboard.services.agent_manager import AgentManager

router = APIRouter(prefix="/api/printers", tags=["printers"])

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# Injected by main.py
_agent_manager: AgentManager | None = None


def set_agent_manager(manager: AgentManager) -> None:
    global _agent_manager
    _agent_manager = manager


def _get_manager() -> AgentManager:
    if _agent_manager is None:
        raise HTTPException(status_code=503, detail="Agent manager not initialized")
    return _agent_manager


# --- Pydantic models --------------------------------------------------

class PrinterCreate(BaseModel):
    name: str
    agent_url: str
    printer_type: str = "auto"  # "auto" triggers detection from /health


class PrinterUpdate(BaseModel):
    name: str | None = None
    agent_url: str | None = None


class ControlRequest(BaseModel):
    command: str


# --- Helper -----------------------------------------------------------

def _printer_to_dict(p: Printer, manager: AgentManager) -> dict[str, Any]:
    status = manager.get_status(p.agent_url)
    return {
        "id": p.id,
        "name": p.name,
        "agent_url": p.agent_url,
        "printer_type": p.printer_type,
        "status": p.status,
        "connected": status.connected if status else False,
        "printing": status.printing if status else False,
        "ink_levels": status.ink_levels if status else {},
        "current_job": status.current_job if status else None,
        "last_seen_at": p.last_seen_at.isoformat() if p.last_seen_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


# --- Routes -----------------------------------------------------------

async def list_printers(
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """GET /api/printers — list all registered printers.

    Returns HTML partial when Accept contains text/html (for HTMX),
    JSON otherwise.
    """
    manager = _get_manager()
    printers = db.query(Printer).all()
    data = [_printer_to_dict(p, manager) for p in printers]

    if "text/html" in request.headers.get("accept", ""):
        return _templates.TemplateResponse(
            request=request,
            name="partials/printer-cards.html",
            context={"printers": data},
        )
    return data


router.add_api_route("", list_printers, methods=["GET"])


async def get_printer_cards(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """GET /api/printers/cards — HTMX partial: printer status card grid."""
    manager = _get_manager()
    printers = db.query(Printer).all()
    data = [_printer_to_dict(p, manager) for p in printers]
    return _templates.TemplateResponse(
        request=request,
        name="partials/printer-cards.html",
        context={"printers": data},
    )


router.add_api_route("/cards", get_printer_cards, methods=["GET"])


async def get_status_dots(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """GET /api/printers/status-dots — HTMX partial: topbar status dots."""
    manager = _get_manager()
    printers = db.query(Printer).all()
    data = [_printer_to_dict(p, manager) for p in printers]
    return _templates.TemplateResponse(
        request=request,
        name="partials/printer-status-dots.html",
        context={"printers": data},
    )


router.add_api_route("/status-dots", get_status_dots, methods=["GET"])


async def get_sidebar_rows(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """GET /api/printers/sidebar-rows — HTMX partial: sidebar printer rows."""
    manager = _get_manager()
    printers = db.query(Printer).all()
    data = [_printer_to_dict(p, manager) for p in printers]
    return _templates.TemplateResponse(
        request=request,
        name="partials/sidebar-printer-rows.html",
        context={"printers": data},
    )


router.add_api_route("/sidebar-rows", get_sidebar_rows, methods=["GET"])


async def get_printer_tabs(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """GET /api/printers/tabs — HTMX partial: printer selector tabs for control page."""
    manager = _get_manager()
    printers = db.query(Printer).all()
    data = [_printer_to_dict(p, manager) for p in printers]
    return _templates.TemplateResponse(
        request=request,
        name="partials/printer-tabs.html",
        context={"printers": data},
    )


router.add_api_route("/tabs", get_printer_tabs, methods=["GET"])


async def register_printer(
    req: PrinterCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """POST /api/printers — register a new printer agent.

    Pings agent_url/health to validate connectivity and auto-detect type.
    """
    manager = _get_manager()

    # Check if agent_url already registered — update instead of rejecting
    existing = db.query(Printer).filter(Printer.agent_url == req.agent_url).first()

    # Try to ping agent /health to validate + auto-detect type
    # May fail if dashboard is cloud and agent is on a private LAN — that's OK
    health = await manager.ping_health(req.agent_url)

    # Resolve printer type
    if req.printer_type == "auto":
        detected = health.get("printer_type", "dtg") if health else "dtg"
    else:
        detected = req.printer_type

    if existing:
        # Re-registration: update name and type, keep the same record
        existing.name = req.name
        existing.printer_type = detected
        db.commit()
        db.refresh(existing)
        printer = existing
    else:
        printer = Printer(
            name=req.name,
            agent_url=req.agent_url,
            printer_type=detected,
            status="offline",
        )
        db.add(printer)
        db.commit()
        db.refresh(printer)

        # Add to live polling immediately (no restart needed)
        manager.add_printer(printer.id, printer.agent_url)

    return {
        "id": printer.id,
        "name": printer.name,
        "agent_url": printer.agent_url,
        "printer_type": printer.printer_type,
        "status": printer.status,
        "created_at": printer.created_at.isoformat() if printer.created_at else None,
    }


router.add_api_route("", register_printer, methods=["POST"])


async def delete_printer(
    printer_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """DELETE /api/printers/{id} — remove a registered printer."""
    manager = _get_manager()
    printer = db.query(Printer).filter(Printer.id == printer_id).first()
    if printer is None:
        raise HTTPException(status_code=404, detail="Printer not found")

    manager.remove_printer(printer.agent_url)
    db.delete(printer)
    db.commit()
    return {"success": True, "deleted_id": printer_id}


router.add_api_route("/{printer_id}", delete_printer, methods=["DELETE"])


async def update_printer(
    printer_id: int,
    req: PrinterUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """PATCH /api/printers/{id} — update printer name or agent URL."""
    manager = _get_manager()
    printer = db.query(Printer).filter(Printer.id == printer_id).first()
    if printer is None:
        raise HTTPException(status_code=404, detail="Printer not found")

    old_url = printer.agent_url

    if req.name is not None:
        printer.name = req.name
    if req.agent_url is not None:
        printer.agent_url = req.agent_url

    db.commit()
    db.refresh(printer)

    # Update polling registry if URL changed
    if req.agent_url and req.agent_url != old_url:
        manager.remove_printer(old_url)
        manager.add_printer(printer.id, printer.agent_url)

    return _printer_to_dict(printer, manager)


router.add_api_route("/{printer_id}", update_printer, methods=["PATCH"])


async def get_printer_live_status(
    printer_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """GET /api/printers/{id}/status — fetch live status directly from agent."""
    manager = _get_manager()
    printer = db.query(Printer).filter(Printer.id == printer_id).first()
    if printer is None:
        raise HTTPException(status_code=404, detail="Printer not found")

    status = manager.get_status(printer.agent_url)
    if status is None:
        raise HTTPException(status_code=503, detail="No status data available yet")

    return {
        "id": printer_id,
        "connected": status.connected,
        "printing": status.printing,
        "ink_levels": status.ink_levels,
        "current_job": status.current_job,
        "position_x": status.position_x,
        "position_y": status.position_y,
    }


router.add_api_route("/{printer_id}/status", get_printer_live_status, methods=["GET"])


async def control_printer(
    printer_id: int,
    req: ControlRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """POST /api/printers/{id}/control — forward command to agent."""
    manager = _get_manager()
    printer = db.query(Printer).filter(Printer.id == printer_id).first()
    if printer is None:
        raise HTTPException(status_code=404, detail="Printer not found")

    ok = await manager.send_control(printer.agent_url, req.command)
    if not ok:
        raise HTTPException(status_code=502, detail="Agent did not accept command")

    return {"success": True, "printer_id": printer_id, "command": req.command}


router.add_api_route("/{printer_id}/control", control_printer, methods=["POST"])


async def printer_sse(request: Request) -> StreamingResponse:
    """GET /api/printers/sse — SSE stream of printer status updates."""
    manager = _get_manager()
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=50)

    def on_update(agent_url: str, status_dict: dict[str, Any]) -> None:
        payload = json.dumps({"agent_url": agent_url, "status": status_dict})
        try:
            queue.put_nowait(f"data: {payload}\n\n")
        except asyncio.QueueFull:
            pass  # drop if client is slow

    manager.subscribe(on_update)

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield msg
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            manager.unsubscribe(on_update)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


router.add_api_route("/sse", printer_sse, methods=["GET"])
