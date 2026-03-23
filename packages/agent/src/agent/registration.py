"""Auto-registration — agent registers itself with the dashboard on startup."""

from __future__ import annotations

import asyncio
import json
import socket
import urllib.request
import urllib.error


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


def _post_json(url: str, data: dict) -> tuple[int, str]:
    """POST JSON using stdlib urllib. Returns (status_code, body)."""
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


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

    dashboard_api = dashboard_url.strip().rstrip("/") + "/api/printers"
    print(f"[agent] Registering with dashboard at {dashboard_api}", flush=True)
    print(f"[agent] Agent URL: {agent_url}", flush=True)

    for attempt in range(5):
        try:
            status, body = await asyncio.get_event_loop().run_in_executor(
                None, _post_json, dashboard_api, payload
            )

            if status in (200, 201):
                print(f"[agent] Registered with dashboard as '{agent_name}' at {agent_url}", flush=True)
                return True
            elif status == 409:
                print(f"[agent] Already registered with dashboard at {agent_url}", flush=True)
                return True
            else:
                print(f"[agent] Registration failed: HTTP {status} {body[:200]}", flush=True)
        except Exception as e:
            wait = 2 ** attempt
            print(f"[agent] Dashboard unreachable ({type(e).__name__}: {e}), retrying in {wait}s...", flush=True)
            await asyncio.sleep(wait)

    print("[agent] Could not register with dashboard after 5 attempts. Will retry later.", flush=True)
    return False
