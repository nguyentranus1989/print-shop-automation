"""AgentManager — DB-driven printer polling with runtime add/remove support.

Loads registered printers from DB on startup, polls each agent every 3 seconds,
updates last_seen_at and status, and marks printers offline after 3 missed polls.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Callable

import httpx

from common.models.printer import PrinterStatus, PrinterType


# Printer is offline after this many consecutive missed polls
_OFFLINE_THRESHOLD = 3


class _AgentEntry:
    """Internal state for a single tracked agent."""

    def __init__(self, printer_id: int, agent_url: str) -> None:
        self.printer_id = printer_id
        self.agent_url = agent_url
        self.status: PrinterStatus | None = None
        self.missed_polls: int = 0


class AgentManager:
    """Manages DB-backed communication with all registered printer agents.

    Usage::

        manager = AgentManager(db_session_factory, poll_interval=3.0)
        await manager.start_polling()  # background task
        manager.add_printer(id=1, url="http://192.168.1.101:8080")
    """

    def __init__(self, db_session_factory: Any, poll_interval: float = 3.0) -> None:
        self._db_factory = db_session_factory
        self._poll_interval = poll_interval
        # agent_url -> entry (mutable at runtime)
        self._entries: dict[str, _AgentEntry] = {}
        self._subscribers: list[Callable[[str, dict[str, Any]], None]] = []
        self._running = False
        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Runtime add / remove
    # ------------------------------------------------------------------

    def add_printer(self, printer_id: int, agent_url: str) -> None:
        """Register a new printer URL to be polled (no restart needed)."""
        if agent_url not in self._entries:
            self._entries[agent_url] = _AgentEntry(printer_id, agent_url)

    def remove_printer(self, agent_url: str) -> None:
        """Deregister a printer URL from polling."""
        self._entries.pop(agent_url, None)

    def get_urls(self) -> list[str]:
        """Return all currently tracked agent URLs."""
        return list(self._entries.keys())

    # ------------------------------------------------------------------
    # Status access
    # ------------------------------------------------------------------

    def get_status(self, agent_url: str) -> PrinterStatus | None:
        """Return cached status for one agent."""
        entry = self._entries.get(agent_url)
        return entry.status if entry else None

    def get_all_statuses(self) -> dict[str, PrinterStatus | None]:
        """Return latest cached status for every registered agent."""
        return {url: e.status for url, e in self._entries.items()}

    # ------------------------------------------------------------------
    # SSE subscription
    # ------------------------------------------------------------------

    def subscribe(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        self._subscribers.remove(callback)

    # ------------------------------------------------------------------
    # Polling lifecycle
    # ------------------------------------------------------------------

    async def start_polling(self) -> None:
        """Load printers from DB and start background polling task."""
        self._load_from_db()
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())

    async def stop_polling(self) -> None:
        """Stop the background polling task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def _load_from_db(self) -> None:
        """Populate _entries from the printers table."""
        # Import here to avoid circular imports at module load time
        from dashboard.db.models import Printer

        db = self._db_factory()
        try:
            printers = db.query(Printer).all()
            for p in printers:
                self.add_printer(p.id, p.agent_url)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        """Continuously poll all agents and persist status to DB."""
        async with httpx.AsyncClient(timeout=3.0) as client:
            while self._running:
                # Snapshot current entries to avoid mutation during iteration
                entries = list(self._entries.values())
                tasks = [self._poll_one(client, e) for e in entries]
                await asyncio.gather(*tasks, return_exceptions=True)
                await asyncio.sleep(self._poll_interval)

    async def _poll_one(self, client: httpx.AsyncClient, entry: _AgentEntry) -> None:
        """Poll a single agent, update status and DB record."""
        url = entry.agent_url
        try:
            resp = await client.get(f"{url.rstrip('/')}/status")
            resp.raise_for_status()
            data = resp.json()

            # Build in-memory status object
            connected = data.get("connected", False)
            printing = data.get("printing", False)
            entry.status = PrinterStatus(
                type=PrinterType(data.get("type", "dtg")),
                connected=connected,
                printing=printing,
                position_x=data.get("position_x", 0.0),
                position_y=data.get("position_y", 0.0),
                ink_levels=data.get("ink_levels", {}),
                current_job=data.get("current_job"),
            )
            entry.missed_polls = 0

            # Compute status string
            if printing:
                status_str = "printing"
            elif connected:
                status_str = "online"
            else:
                status_str = "offline"

            self._persist_status(entry.printer_id, status_str, connected=True)

            # Notify SSE subscribers
            for cb in self._subscribers:
                cb(url, data)

        except Exception:
            entry.missed_polls += 1
            if entry.missed_polls >= _OFFLINE_THRESHOLD:
                entry.status = PrinterStatus(
                    type=PrinterType.DTG,
                    connected=False,
                )
                self._persist_status(entry.printer_id, "offline", connected=False)

    def _persist_status(
        self, printer_id: int, status_str: str, connected: bool
    ) -> None:
        """Write status and last_seen_at to DB (fire-and-forget, swallows errors)."""
        from dashboard.db.models import Printer

        db = self._db_factory()
        try:
            printer = db.query(Printer).filter(Printer.id == printer_id).first()
            if printer:
                printer.status = status_str
                printer.connected = int(connected)
                if connected:
                    printer.last_seen_at = datetime.utcnow()
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Control commands
    # ------------------------------------------------------------------

    async def send_job(self, agent_url: str, job_payload: dict[str, Any]) -> bool:
        """POST a job to an agent's /jobs endpoint."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{agent_url.rstrip('/')}/jobs", json=job_payload
                )
                resp.raise_for_status()
                return True
        except Exception:
            return False

    async def send_control(self, agent_url: str, command: str) -> bool:
        """POST a control command to an agent."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{agent_url.rstrip('/')}/control/{command}"
                )
                resp.raise_for_status()
                return True
        except Exception:
            return False

    async def ping_health(self, agent_url: str) -> dict[str, Any] | None:
        """GET /health from an agent URL; returns parsed JSON or None on failure."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{agent_url.rstrip('/')}/health")
                resp.raise_for_status()
                return resp.json()
        except Exception:
            return None
