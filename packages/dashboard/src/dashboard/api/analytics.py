"""Analytics API — aggregated stats for dashboard charts."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from dashboard.db.database import get_db
from dashboard.db.models import InkUsage, Job

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# --- Helper -----------------------------------------------------------

def _today_start() -> datetime:
    now = datetime.utcnow()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


# --- Routes -----------------------------------------------------------

def analytics_summary(db: Session = Depends(get_db)) -> dict[str, Any]:
    """GET /api/analytics/summary — today's job stats."""
    today = _today_start()

    total_today = db.query(func.count(Job.id)).filter(Job.created_at >= today).scalar() or 0
    completed_today = (
        db.query(func.count(Job.id))
        .filter(Job.created_at >= today, Job.status == "completed")
        .scalar()
        or 0
    )
    failed_today = (
        db.query(func.count(Job.id))
        .filter(Job.created_at >= today, Job.status == "failed")
        .scalar()
        or 0
    )
    pending = db.query(func.count(Job.id)).filter(Job.status == "pending").scalar() or 0

    return {
        "date": today.date().isoformat(),
        "total_today": total_today,
        "completed_today": completed_today,
        "failed_today": failed_today,
        "pending_in_queue": pending,
        "success_rate": round(completed_today / total_today * 100, 1) if total_today > 0 else 0.0,
    }


router.add_api_route("/summary", analytics_summary, methods=["GET"])


@router.get("/kpi-strip", response_class=HTMLResponse)
def kpi_strip(request: Request, db: Session = Depends(get_db)):
    """Returns server-rendered KPI strip HTML partial for HTMX swap."""
    stats = analytics_summary(db)
    printing = db.query(func.count(Job.id)).filter(Job.status == "printing").scalar() or 0
    return _templates.TemplateResponse(
        request=request,
        name="partials/kpi-strip.html",
        context={"pending": stats["pending_in_queue"], "printing": printing,
                 "completed": stats["completed_today"], "failed": stats["failed_today"]},
    )


def analytics_throughput(
    hours: int = 24,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """GET /api/analytics/throughput — completed jobs per hour for last N hours."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    rows = (
        db.query(
            func.strftime("%Y-%m-%dT%H:00:00", Job.completed_at).label("hour"),
            func.count(Job.id).label("count"),
        )
        .filter(Job.status == "completed", Job.completed_at >= cutoff)
        .group_by("hour")
        .order_by("hour")
        .all()
    )

    return [{"hour": row.hour, "count": row.count} for row in rows]


router.add_api_route("/throughput", analytics_throughput, methods=["GET"])


def analytics_ink(
    printer_id: int | None = None,
    hours: int = 24,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """GET /api/analytics/ink — ink level history for last N hours."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    query = db.query(InkUsage).filter(InkUsage.recorded_at >= cutoff)
    if printer_id is not None:
        query = query.filter(InkUsage.printer_id == printer_id)

    rows = query.order_by(InkUsage.recorded_at.asc()).all()

    return [
        {
            "printer_id": row.printer_id,
            "recorded_at": row.recorded_at.isoformat(),
            "cyan": row.cyan,
            "magenta": row.magenta,
            "yellow": row.yellow,
            "black": row.black,
            "white": row.white,
        }
        for row in rows
    ]


router.add_api_route("/ink", analytics_ink, methods=["GET"])
