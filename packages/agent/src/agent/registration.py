"""Auto-registration — agent registers itself with the dashboard on startup."""

from __future__ import annotations

import asyncio
import socket

import httpx


def detect_lan_ip() -> str:
    """Detect this machine's LAN IP by connecting to a public DNS (no data sent)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


async def register_with_dashboard(
    dashboard_url: str,
    agent_name: str,
    agent_port: int,
    printer_type: str,
) -> bool:
    """POST to dashboard /api/printers to register this agent.

    Retries up to 5 times with backoff if dashboard is unreachable.
    Returns True on success.
    """
    lan_ip = detect_lan_ip()
    agent_url = f"http://{lan_ip}:{agent_port}"

    payload = {
        "name": agent_name,
        "agent_url": agent_url,
        "printer_type": printer_type,
    }

    dashboard_api = dashboard_url.rstrip("/") + "/api/printers"

    for attempt in range(5):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(dashboard_api, json=payload)

            if resp.status_code in (200, 201):
                print(f"[agent] Registered with dashboard as '{agent_name}' at {agent_url}", flush=True)
                return True
            elif resp.status_code == 409:
                # Already registered — that's fine
                print(f"[agent] Already registered with dashboard at {agent_url}", flush=True)
                return True
            else:
                print(f"[agent] Registration failed: {resp.status_code} {resp.text}", flush=True)
        except Exception as e:
            wait = 2 ** attempt
            print(f"[agent] Dashboard unreachable ({e}), retrying in {wait}s...", flush=True)
            await asyncio.sleep(wait)

    print("[agent] Could not register with dashboard after 5 attempts. Will retry later.", flush=True)
    return False
