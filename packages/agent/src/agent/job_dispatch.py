"""Job dispatch — uses long-polling for near-instant job pickup."""

from __future__ import annotations

import asyncio
import json
import ssl
import urllib.request
import urllib.error

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


async def job_dispatch_loop(
    dashboard_url: str,
    printer_type: str,
    inject_fn,
    interval: float = 2.0,
    agent_printer_id: int | None = None,
) -> None:
    """Long-poll dashboard for jobs. Picks up instantly when job is created."""
    await asyncio.sleep(3)
    print("[dispatch] Started — waiting for jobs (long-poll)", flush=True)

    while True:
        try:
            # Resolve printer_id if not known
            if agent_printer_id is None:
                from agent.registration import get_registered_printer_id
                agent_printer_id = get_registered_printer_id()

            # Long-poll: blocks up to 10s, returns instantly when job appears
            params = f"printer_type={printer_type}&timeout=10"
            if agent_printer_id:
                params += f"&printer_id={agent_printer_id}"
            url = f"{dashboard_url}/api/jobs/next?{params}"

            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")

            with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                if not body or not body.strip():
                    await asyncio.sleep(2)
                    continue
                data = json.loads(body)

            job = data.get("job")
            if not job:
                continue  # timeout, no job — retry immediately

            job_id = job["id"]
            prn_path = job["prn_path"]
            order_id = job.get("order_id", "unknown")

            print(f"[dispatch] Picking up job {order_id} — {prn_path}", flush=True)
            _patch_job(dashboard_url, job_id, "injecting")

            try:
                success = await inject_fn(prn_path, order_id)
            except Exception as e:
                print(f"[dispatch] Injection error: {e}", flush=True)
                success = False

            if success:
                _patch_job(dashboard_url, job_id, "sent")
                print(f"[dispatch] Job {order_id} — SENT to PrintExp", flush=True)
            else:
                _patch_job(dashboard_url, job_id, "failed", "Injection failed")
                print(f"[dispatch] Job {order_id} — FAILED", flush=True)

            # Check for more jobs immediately (batch mode)
            await asyncio.sleep(0.5)

        except urllib.error.URLError:
            await asyncio.sleep(5)  # dashboard unreachable, retry
        except Exception as e:
            print(f"[dispatch] Error: {e}", flush=True)
            await asyncio.sleep(2)


def _patch_job(dashboard_url: str, job_id: str, status: str, error_msg: str | None = None) -> None:
    """Update job status on dashboard."""
    url = f"{dashboard_url}/api/jobs/{job_id}"
    data = {"status": status}
    if error_msg:
        data["error_message"] = error_msg

    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="PATCH")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=5, context=_ssl_ctx):
            pass
    except Exception as e:
        print(f"[dispatch] Failed to update job {job_id}: {e}", flush=True)
