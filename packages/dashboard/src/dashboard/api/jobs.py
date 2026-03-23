"""Jobs API — CRUD for the print job queue."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from common.models.job import JobStatus
from dashboard.db.database import get_db
from dashboard.services.job_queue import JobQueue

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# --- Request / Response models ----------------------------------------

class CreateJobRequest(BaseModel):
    order_id: str
    prn_path: str
    printer_type: str
    copies: int = 1
    notes: Optional[str] = None


class UpdateJobRequest(BaseModel):
    status: str
    error_message: Optional[str] = None


def _job_to_dict(job: Any) -> dict[str, Any]:
    return {
        "id": job.id,
        "order_id": job.order_id,
        "prn_path": job.prn_path,
        "printer_type": job.printer_type,
        "status": job.status,
        "copies": job.copies,
        "notes": job.notes,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "printer_id": job.printer_id,
    }


# --- Routes -----------------------------------------------------------

def list_jobs(
    status: Optional[str] = None,
    printer_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """GET /api/jobs — list jobs with optional filters."""
    queue = JobQueue(db)
    jobs = queue.list_jobs(status=status, printer_type=printer_type, limit=limit, offset=offset)
    return [_job_to_dict(j) for j in jobs]


router.add_api_route("", list_jobs, methods=["GET"])


def create_job(req: CreateJobRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """POST /api/jobs — create a new print job."""
    queue = JobQueue(db)
    job = queue.add_job(
        order_id=req.order_id,
        prn_path=req.prn_path,
        printer_type=req.printer_type,
        copies=req.copies,
        notes=req.notes,
    )
    return _job_to_dict(job)


router.add_api_route("", create_job, methods=["POST"])


def update_job(
    job_id: str,
    req: UpdateJobRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """PATCH /api/jobs/{job_id} — update job status."""
    try:
        new_status = JobStatus(req.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {req.status!r}")

    queue = JobQueue(db)
    job = queue.update_status(job_id, new_status, req.error_message)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_dict(job)


router.add_api_route("/{job_id}", update_job, methods=["PATCH"])


def cancel_job(job_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """DELETE /api/jobs/{job_id} — cancel a pending/queued job."""
    queue = JobQueue(db)
    job = queue.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    terminal = {JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value}
    if job.status in terminal:
        raise HTTPException(status_code=409, detail=f"Cannot cancel job in state: {job.status!r}")

    updated = queue.update_status(job_id, JobStatus.CANCELLED)
    return _job_to_dict(updated)


router.add_api_route("/{job_id}", cancel_job, methods=["DELETE"])
