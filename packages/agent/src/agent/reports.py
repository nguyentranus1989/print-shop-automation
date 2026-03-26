"""UV PrintExp job history reports — queries StatisticData.db.

Provides FastAPI router with endpoints for production reporting.
The DB path is auto-detected from the agent's PrintExp directory.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

router = APIRouter(prefix="/reports", tags=["reports"])

_db_path: str | None = None

STATUS_MAP = {0: "Pending", 1: "Printing", 2: "Completed", 3: "Cancelled", 4: "Error"}


def set_db_path(printexp_dir: str) -> None:
    """Set the StatisticData.db path from PrintExp installation dir."""
    global _db_path
    p = Path(printexp_dir) / "Data" / "StatisticData.db"
    if p.exists():
        _db_path = str(p)


def _get_db() -> sqlite3.Connection:
    if not _db_path:
        raise RuntimeError("StatisticData.db not configured")
    return sqlite3.connect(_db_path)


@router.get("/summary")
def report_summary() -> dict[str, Any]:
    db = _get_db()
    cur = db.cursor()

    cur.execute("SELECT count(*) FROM TaskStatistic")
    total = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM TaskStatistic WHERE PrintedStatus=2")
    completed = cur.fetchone()[0]

    cur.execute("SELECT sum(PrintedArea), sum(PrintedTimeCost) FROM TaskStatistic WHERE PrintedStatus=2")
    row = cur.fetchone()
    total_area = row[0] or 0
    total_time = row[1] or 0

    cur.execute("SELECT count(DISTINCT TaskName) FROM TaskStatistic")
    unique = cur.fetchone()[0]

    cur.execute("SELECT min(StartPrintTimeTxt), max(EndPrintTimeTxt) FROM TaskStatistic")
    dates = cur.fetchone()

    cur.execute("SELECT sum(PrintInkCost) FROM TaskStatistic")
    ink = cur.fetchone()[0] or 0

    db.close()
    return {
        "total_jobs": total,
        "completed": completed,
        "unique_designs": unique,
        "total_area_m2": round(total_area, 2),
        "total_time_s": total_time,
        "total_time_display": f"{total_time // 3600}h {(total_time % 3600) // 60}m",
        "total_ink_cost": round(ink, 2),
        "date_from": dates[0] or "",
        "date_to": dates[1] or "",
    }


@router.get("/recent")
def report_recent(limit: int = Query(default=20, le=100)) -> list[dict[str, Any]]:
    db = _get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT Id, TaskName, StartPrintTimeTxt, EndPrintTimeTxt,
               PrintedStatus, PrintCopys, PrintedCopys,
               PrintWidth, PrintLength, PrintedArea,
               PrintedProgress, PrintedTimeCost, PrintPassMode,
               PrnDpiX, PrnDpiY, PrintInkCost, JsonFields
        FROM TaskStatistic ORDER BY Id DESC LIMIT ?
    """, (limit,))

    rows = []
    for r in cur.fetchall():
        entry = {
            "id": r[0], "name": r[1],
            "start": r[2] or "", "end": r[3] or "",
            "status": STATUS_MAP.get(r[4], f"?{r[4]}"),
            "status_code": r[4],
            "copies_total": r[5] or 0, "copies_done": r[6] or 0,
            "width_mm": round(r[7] or 0, 1), "length_mm": round(r[8] or 0, 1),
            "area_m2": round(r[9] or 0, 4),
            "progress": round(r[10] or 0, 1),
            "time_s": r[11] or 0,
            "pass_mode": r[12] or "",
            "dpi": f"{r[13] or 0}x{r[14] or 0}",
            "ink_cost": round(r[15] or 0, 2),
        }
        if r[16]:
            try:
                jf = json.loads(r[16])
                entry["mirror"] = bool(jf.get("CWC_MirrorHorz", 0))
                entry["copies_layout"] = f"{jf.get('HorCopys', 1)}x{jf.get('VerCopys', 1)}"
            except (json.JSONDecodeError, TypeError):
                pass
        rows.append(entry)

    db.close()
    return rows


@router.get("/daily")
def report_daily(days: int = Query(default=30, le=365)) -> list[dict[str, Any]]:
    db = _get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT date(StartPrintTimeTxt) as day,
               count(*) as jobs,
               count(DISTINCT TaskName) as designs,
               sum(PrintedCopys) as copies,
               sum(PrintedArea) as area,
               sum(PrintedTimeCost) as time_s,
               sum(PrintInkCost) as ink
        FROM TaskStatistic
        WHERE PrintedStatus=2
        GROUP BY day
        ORDER BY day DESC
        LIMIT ?
    """, (days,))

    rows = [
        {
            "date": r[0], "jobs": r[1], "designs": r[2],
            "copies": r[3] or 0, "area_m2": round(r[4] or 0, 3),
            "time_s": r[5] or 0, "ink_cost": round(r[6] or 0, 2),
        }
        for r in cur.fetchall()
    ]
    db.close()
    return rows


@router.get("/ink")
def report_ink() -> list[dict[str, Any]]:
    db = _get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT InkName, count(*) as jobs,
               sum(PrintCost) as print_cost,
               sum(FlashCost) as flash_cost
        FROM InkCostCMYK
        GROUP BY InkName
        ORDER BY print_cost DESC
    """)
    rows = [
        {"channel": r[0], "jobs": r[1],
         "print_cost": round(r[2] or 0, 2), "flash_cost": round(r[3] or 0, 2)}
        for r in cur.fetchall()
    ]
    db.close()
    return rows
