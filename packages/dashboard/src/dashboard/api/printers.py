"""Printers API — status, control, SSE stream."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from dashboard.db.database import get_db
from dashboard.db.models import Printer
from dashboard.services.agent_manager import AgentManager

router = APIRouter(prefix="/api/printers", tags=["printers"])

# Injected by main.py
_agent_manager: AgentManager | None = None


def set_agent_manager(manager: AgentManager) -> None:
    global _agent_manager
    _agent_manager = manager


def _get_manager() -> AgentManager:
    if _agent_manager is None:
        raise HTTPException(status_code=503, detail="Agent manager not initialized")
    return _agent_manager


class ControlRequest(BaseModel):
    command: str


# --- Routes -----------------------------------------------------------

def get_all_printers(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """GET /api/printers — list all registered printers with current status."""
    manager = _get_manager()
    printers = db.query(Printer).all()
    result = []
    for p in printers:
        status = manager.get_status(p.agent_url)
        result.append(
            {
                "id": p.id,
                "name": p.name,
                "agent_url": p.agent_url,
                "printer_type": p.printer_type,
                "connected": status.connected if status else False,
                "printing": status.printing if status else False,
                "ink_levels": status.ink_levels if status else {},
                "current_job": status.current_job if status else None,
                "last_seen_at": p.last_seen_at.isoformat() if p.last_seen_at else None,
            }
        )
    return result


router.add_api_route("", get_all_printers, methods=["GET"])


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
    """GET /api/printers/sse — SSE stream of printer status updates.

    Each event is a JSON object: {"agent_url": ..., "status": {...}}
    """
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
                    # Send keepalive comment so client doesn't time out
                    yield ": keepalive\n\n"
        finally:
            manager.unsubscribe(on_update)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


router.add_api_route("/sse", printer_sse, methods=["GET"])
