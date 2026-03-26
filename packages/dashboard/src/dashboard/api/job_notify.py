"""Long-poll endpoint for agents waiting for jobs."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from dashboard.db.database import get_db
from dashboard.db.models import Job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Event that gets set whenever a new job is created
_new_job_event = asyncio.Event()


def notify_new_job() -> None:
    """Call this when a new job is created to wake up waiting agents."""
    _new_job_event.set()


async def wait_for_next_job(
    printer_type: str = Query(...),
    printer_id: Optional[int] = Query(default=None),
    timeout: int = Query(default=30, le=60),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """GET /api/jobs/next — long-poll for the next pending job.

    Blocks up to `timeout` seconds. Returns immediately if a job is available.
    Returns {"job": null} if timeout expires with no job.
    """
    for _ in range(timeout * 2):  # check every 0.5s
        # Query for pending jobs matching criteria
        query = db.query(Job).filter(
            Job.status == "pending",
            Job.printer_type == printer_type,
        )
        if printer_id is not None:
            query = query.filter(
                (Job.printer_id == printer_id) | (Job.printer_id.is_(None))
            )
        query = query.order_by(Job.created_at.asc())
        job = query.first()

        if job:
            return {
                "job": {
                    "id": job.id,
                    "order_id": job.order_id,
                    "prn_path": job.prn_path,
                    "printer_type": job.printer_type,
                    "printer_id": job.printer_id,
                    "notes": job.notes,
                }
            }

        # Wait for notification or timeout
        _new_job_event.clear()
        try:
            await asyncio.wait_for(_new_job_event.wait(), timeout=0.5)
        except asyncio.TimeoutError:
            pass

    return {"job": None}


router.add_api_route("/next", wait_for_next_job, methods=["GET"])
