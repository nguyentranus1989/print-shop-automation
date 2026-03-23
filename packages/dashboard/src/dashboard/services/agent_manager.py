"""AgentManager — polls printer agents and broadcasts status via SSE.

Maintains a registry of agent URLs, polls them every 2 seconds,
and exposes the latest status for SSE clients.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

import httpx

from common.models.printer import PrinterStatus, PrinterType


class AgentManager:
    """Manages communication with all registered printer agents.

    Usage::

        manager = AgentManager(["http://192.168.1.101:8080", ...])
        await manager.start_polling()   # starts background task
    """

    def __init__(self, agent_urls: list[str], poll_interval: float = 2.0) -> None:
        self._urls = agent_urls
        self._poll_interval = poll_interval
        # Latest status per agent URL
        self._statuses: dict[str, PrinterStatus | None] = {url: None for url in agent_urls}
        # SSE subscriber callbacks: called with (agent_url, status_dict)
        self._subscribers: list[Callable[[str, dict[str, Any]], None]] = []
        self._running = False
        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Status access
    # ------------------------------------------------------------------

    def get_all_statuses(self) -> dict[str, PrinterStatus | None]:
        """Return the latest cached status for every agent."""
        return dict(self._statuses)

    def get_status(self, agent_url: str) -> PrinterStatus | None:
        """Return cached status for one agent."""
        return self._statuses.get(agent_url)

    # ------------------------------------------------------------------
    # SSE subscription
    # ------------------------------------------------------------------

    def subscribe(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        """Register a callback to be called on each status update."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        self._subscribers.remove(callback)

    # ------------------------------------------------------------------
    # Polling loop
    # ------------------------------------------------------------------

    async def start_polling(self) -> None:
        """Start the background polling task."""
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

    async def _poll_loop(self) -> None:
        """Continuously poll all agents and notify subscribers."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            while self._running:
                tasks = [self._poll_one(client, url) for url in self._urls]
                await asyncio.gather(*tasks, return_exceptions=True)
                await asyncio.sleep(self._poll_interval)

    async def _poll_one(self, client: httpx.AsyncClient, url: str) -> None:
        """Poll a single agent's /status endpoint."""
        try:
            resp = await client.get(f"{url.rstrip('/')}/status")
            resp.raise_for_status()
            data = resp.json()
            status = PrinterStatus(
                type=PrinterType(data.get("type", "dtg")),
                connected=data.get("connected", False),
                printing=data.get("printing", False),
                position_x=data.get("position_x", 0.0),
                position_y=data.get("position_y", 0.0),
                ink_levels=data.get("ink_levels", {}),
                current_job=data.get("current_job"),
            )
            self._statuses[url] = status
            # Notify SSE subscribers
            for cb in self._subscribers:
                cb(url, data)
        except Exception:
            # Mark as disconnected on any error
            self._statuses[url] = PrinterStatus(
                type=PrinterType.DTG,
                connected=False,
            )

    # ------------------------------------------------------------------
    # Control commands
    # ------------------------------------------------------------------

    async def send_job(self, agent_url: str, job_payload: dict[str, Any]) -> bool:
        """POST a job to an agent's /jobs endpoint."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(f"{agent_url.rstrip('/')}/jobs", json=job_payload)
                resp.raise_for_status()
                return True
        except Exception:
            return False

    async def send_control(self, agent_url: str, command: str) -> bool:
        """POST a control command to an agent."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"{agent_url.rstrip('/')}/control/{command}")
                resp.raise_for_status()
                return True
        except Exception:
            return False
