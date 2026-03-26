"""Jobs API — CRUD for the print job queue, with HTMX HTML partials."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from common.models.job import JobStatus
from dashboard.db.database import get_db
from dashboard.services.job_queue import JobQueue

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# --- Request / Response models ----------------------------------------

class CreateJobRequest(BaseModel):
    order_id: str
    prn_path: str
    printer_type: str
    printer_id: Optional[int] = None
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
    request: Request,
    status: Optional[str] = None,
    printer_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """GET /api/jobs — list jobs. Returns HTML rows for HTMX, JSON otherwise."""
    queue = JobQueue(db)
    jobs = queue.list_jobs(status=status, printer_type=printer_type, limit=limit, offset=offset)
    job_list = [_job_to_dict(j) for j in jobs]

    # HTMX request → return HTML table rows
    if request.headers.get("hx-request"):
        if not job_list:
            return HTMLResponse(
                '<tr><td colspan="8" style="padding:0;">'
                '<div class="empty-state" style="padding:40px 24px;">'
                '<i data-lucide="inbox" style="width:36px;height:36px;color:var(--text-mut);"></i>'
                '<div class="empty-state-title">No jobs in queue</div>'
                '<div class="empty-state-sub">Add a print job to get started</div>'
                '</div></td></tr>'
            )
        rows = ""
        for i, j in enumerate(job_list, 1):
            status_cls = {
                "pending": "badge-warn",
                "queued": "badge-info",
                "injecting": "badge-info",
                "sent": "badge-ok",
                "printing": "badge-accent",
                "completed": "badge-ok",
                "failed": "badge-err",
                "cancelled": "badge-mut",
            }.get(j["status"], "")

            fname = j["prn_path"].replace("\\", "/").split("/")[-1] if j["prn_path"] else "—"
            notes = j["notes"] or "—"
            order = j["order_id"] or "—"
            ptype = (j["printer_type"] or "—").upper()
            status_label = (j["status"] or "—").capitalize()

            rows += (
                f'<tr>'
                f'<td>{i}</td>'
                f'<td title="{j["prn_path"]}">{fname}</td>'
                f'<td>{order}</td>'
                f'<td>{notes}</td>'
                f'<td><span class="badge {status_cls}">{status_label}</span></td>'
                f'<td>{ptype}</td>'
                f'<td>—</td>'
                f'<td>'
            )
            if j["status"] in ("pending", "queued"):
                rows += (
                    f'<button class="btn btn-ghost btn-sm" '
                    f'hx-delete="/api/jobs/{j["id"]}" hx-swap="none" '
                    f'hx-on::after-request="htmx.trigger(\'#job-tbody\',\'load\')" '
                    f'title="Cancel">✕</button>'
                )
            rows += '</td></tr>'

        return HTMLResponse(rows)

    # Regular API request → return JSON
    return job_list


router.add_api_route("", list_jobs, methods=["GET"])


def create_job(req: CreateJobRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """POST /api/jobs — create a new print job."""
    from dashboard.api.job_notify import notify_new_job

    queue = JobQueue(db)
    job = queue.add_job(
        order_id=req.order_id,
        prn_path=req.prn_path,
        printer_type=req.printer_type,
        printer_id=req.printer_id,
        copies=req.copies,
        notes=req.notes,
    )

    # Wake up any agents waiting via long-poll
    notify_new_job()

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
