"""Auto-registration and heartbeat — agent registers and pushes status to dashboard."""

from __future__ import annotations

import asyncio
import json
import socket
import ssl
import urllib.request
import urllib.error

# Allow self-signed / unverified SSL certs (common in local/internal setups)
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


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
        resp = urllib.request.urlopen(req, timeout=10, context=_ssl_ctx)
        return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


_registered_printer_id: int | None = None


def get_registered_printer_id() -> int | None:
    """Return the printer_id assigned by the dashboard, or None if not registered."""
    return _registered_printer_id


async def register_with_dashboard(
    dashboard_url: str,
    agent_name: str,
    agent_port: int,
    printer_type: str,
) -> bool:
    """POST to dashboard /api/printers to register this agent.

    Retries up to 5 times with backoff if dashboard is unreachable.
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
                global _registered_printer_id
                try:
                    data = json.loads(body)
                    _registered_printer_id = data.get("id")
                    print(f"[agent] Registered as printer_id={_registered_printer_id}", flush=True)
                except Exception:
                    pass
                print(f"[agent] Registered with dashboard as '{agent_name}' at {agent_url}", flush=True)
                return True
            elif status == 409:
                # Try to get our printer_id from existing registration
                global _registered_printer_id
                try:
                    data = json.loads(body)
                    _registered_printer_id = data.get("id")
                except Exception:
                    pass
                print(f"[agent] Already registered (printer_id={_registered_printer_id})", flush=True)
                return True
            else:
                print(f"[agent] Registration failed: HTTP {status} {body[:200]}", flush=True)
        except Exception as e:
            wait = 2 ** attempt
            print(f"[agent] Dashboard unreachable ({type(e).__name__}: {e}), retrying in {wait}s...", flush=True)
            await asyncio.sleep(wait)

    print("[agent] Could not register with dashboard after 5 attempts. Will retry later.", flush=True)
    return False


async def heartbeat_loop(
    dashboard_url: str,
    agent_port: int,
    printer_type: str,
    get_status_fn,
    interval: float = 10.0,
) -> None:
    """Periodically push agent status to the dashboard heartbeat endpoint.

    Runs forever as a background task.
    """
    lan_ip = detect_lan_ip()
    agent_url = f"http://{lan_ip}:{agent_port}"
    heartbeat_api = dashboard_url.strip().rstrip("/") + "/api/printers/heartbeat"

    # Wait a bit for the agent to fully start
    await asyncio.sleep(3)

    while True:
        try:
            status = await get_status_fn()
            payload = {
                "agent_url": agent_url,
                "connected": status.connected,
                "printing": status.printing,
                "printer_type": printer_type,
                "ink_levels": status.ink_levels or {},
                "current_job": status.current_job,
                "position_x": status.position_x,
                "position_y": status.position_y,
            }

            code, _ = await asyncio.get_event_loop().run_in_executor(
                None, _post_json, heartbeat_api, payload
            )

            if code == 200:
                pass  # silent success
            elif code == 404:
                print("[agent] Heartbeat: not registered yet, will retry registration", flush=True)
            else:
                print(f"[agent] Heartbeat: HTTP {code}", flush=True)
        except Exception:
            pass  # silent failure, will retry next interval

        await asyncio.sleep(interval)
