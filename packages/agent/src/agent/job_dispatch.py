"""Job dispatch loop — polls dashboard for pending jobs and injects them."""

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
    interval: float = 5.0,
    agent_printer_id: int | None = None,
) -> None:
    """Poll dashboard for pending jobs, inject them via backend.

    Args:
        dashboard_url: Dashboard base URL (e.g. http://localhost:8000)
        printer_type: Filter jobs by this type (e.g. "dtf")
        inject_fn: async callable(prn_path, job_name) -> bool
        interval: Seconds between polls
        agent_printer_id: This agent's printer ID in dashboard DB
    """
    # Wait for agent to fully start
    await asyncio.sleep(3)
    print(f"[dispatch] Started — polling {dashboard_url} for {printer_type} jobs every {interval}s", flush=True)

    while True:
        try:
            # Get pending jobs for our printer type
            url = f"{dashboard_url}/api/jobs?status=pending&printer_type={printer_type}"
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")

            with urllib.request.urlopen(req, timeout=5, context=_ssl_ctx) as resp:
                jobs = json.loads(resp.read().decode("utf-8"))

            if not jobs:
                await asyncio.sleep(interval)
                continue

            # Filter: pick jobs assigned to us, or unassigned, or any if we don't know our ID
            my_jobs = []
            for j in jobs:
                pid = j.get("printer_id")
                if pid is None:
                    my_jobs.append(j)  # unassigned job — take it
                elif agent_printer_id is None:
                    my_jobs.append(j)  # we don't know our ID — take any of our type
                elif pid == agent_printer_id:
                    my_jobs.append(j)  # explicitly assigned to us

            if not my_jobs:
                await asyncio.sleep(interval)
                continue

            # Process first matching job
            job = my_jobs[0]
            job_id = job["id"]
            prn_path = job["prn_path"]
            order_id = job.get("order_id", "unknown")

            print(f"[dispatch] Picking up job {order_id} — {prn_path}", flush=True)

            # Update status to "injecting"
            _patch_job(dashboard_url, job_id, "injecting")

            # Inject via backend
            try:
                success = await inject_fn(prn_path, order_id)
            except Exception as e:
                print(f"[dispatch] Injection error: {e}", flush=True)
                success = False

            if success:
                _patch_job(dashboard_url, job_id, "completed")
                print(f"[dispatch] Job {order_id} — COMPLETED", flush=True)
            else:
                _patch_job(dashboard_url, job_id, "failed", "Injection failed")
                print(f"[dispatch] Job {order_id} — FAILED", flush=True)

        except urllib.error.URLError:
            pass
        except Exception as e:
            print(f"[dispatch] Error: {e}", flush=True)

        await asyncio.sleep(interval)


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
