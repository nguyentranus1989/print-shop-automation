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
    interval: float = 2.0,
    agent_printer_id: int | None = None,
) -> None:
    """Poll dashboard for pending jobs, inject them via backend.

    Polls every `interval` seconds. After processing a job, immediately
    checks for more (no wait). This gives near-instant pickup for batches.
    """
    await asyncio.sleep(3)
    print(f"[dispatch] Started — polling every {interval}s", flush=True)

    while True:
        processed = False
        try:
            # Resolve our printer_id if not set yet
            if agent_printer_id is None:
                from agent.registration import get_registered_printer_id
                agent_printer_id = get_registered_printer_id()

            # Get pending jobs
            url = f"{dashboard_url}/api/jobs?status=pending&printer_type={printer_type}"
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")

            with urllib.request.urlopen(req, timeout=5, context=_ssl_ctx) as resp:
                jobs = json.loads(resp.read().decode("utf-8"))

            if not jobs:
                await asyncio.sleep(interval)
                continue

            # Filter: pick jobs assigned to us or unassigned
            my_jobs = []
            for j in jobs:
                pid = j.get("printer_id")
                if pid is None:
                    my_jobs.append(j)
                elif agent_printer_id and pid == agent_printer_id:
                    my_jobs.append(j)

            if not my_jobs:
                await asyncio.sleep(interval)
                continue

            # Process first job
            job = my_jobs[0]
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
                _patch_job(dashboard_url, job_id, "completed")
                print(f"[dispatch] Job {order_id} — COMPLETED", flush=True)
            else:
                _patch_job(dashboard_url, job_id, "failed", "Injection failed")
                print(f"[dispatch] Job {order_id} — FAILED", flush=True)

            processed = True

        except urllib.error.URLError:
            pass
        except Exception as e:
            print(f"[dispatch] Error: {e}", flush=True)

        # If we just processed a job, check again immediately (batch mode)
        if processed:
            await asyncio.sleep(0.5)
        else:
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
