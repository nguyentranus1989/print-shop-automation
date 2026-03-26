"""PrintExp job history reports — supports multiple data sources.

- UV / DTF v5.8.2: StatisticData.db (SQLite)
- DTG v5.7.7: Data/Statistic/YYYY-MM-DD.ini files
- DTF v5.7.6: No history (returns empty)

The agent auto-detects which source is available based on printexp_dir.
"""
from __future__ import annotations

import configparser
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

router = APIRouter(prefix="/reports", tags=["reports"])

_db_path: str | None = None
_stat_dir: str | None = None
_source: str = "none"  # "sqlite", "ini", "none"

STATUS_MAP = {0: "Pending", 1: "Printing", 2: "Completed", 3: "Cancelled", 4: "Error"}

# DTG ink channel names (indices 0-31, typically only 0-8 used)
DTG_INK_CHANNELS = {
    0: "C", 1: "M", 2: "Y", 3: "K",
    4: "Lc", 5: "Lm", 6: "W1", 7: "W2",
    8: "Pre", 9: "C2", 10: "M2", 11: "Y2", 12: "K2",
}


def set_db_path(printexp_dir: str) -> None:
    """Auto-detect report source from PrintExp directory."""
    global _db_path, _stat_dir, _source

    db = Path(printexp_dir) / "Data" / "StatisticData.db"
    stat = Path(printexp_dir) / "Data" / "Statistic"

    if db.exists():
        _db_path = str(db)
        _source = "sqlite"
    elif stat.is_dir() and any(stat.glob("*.ini")):
        _stat_dir = str(stat)
        _source = "ini"
    else:
        _source = "none"


# --- SQLite helpers (UV / DTF v5.8.2) ---

def _get_db() -> sqlite3.Connection:
    if not _db_path:
        raise RuntimeError("StatisticData.db not configured")
    return sqlite3.connect(_db_path)


# --- INI helpers (DTG) ---

def _parse_daily_ini(path: str) -> dict[str, Any]:
    """Parse a DTG daily statistics INI file."""
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8-sig")

    planned = cp.getint("APP_STATISTIC_CAPACITY", "nPlanPcs", fallback=0)
    actual = cp.getint("APP_STATISTIC_CAPACITY", "nCurPcs", fallback=0)

    ink = {}
    if cp.has_section("APP_STATISTIC_TOTAL_INK"):
        for key, val in cp.items("APP_STATISTIC_TOTAL_INK"):
            idx = int(key)
            amount = float(val)
            if amount > 0:
                name = DTG_INK_CHANNELS.get(idx, f"Ch{idx}")
                ink[name] = amount

    return {"planned": planned, "actual": actual, "ink": ink}


def _list_daily_inis() -> list[tuple[str, str]]:
    """List (date_str, file_path) for all daily INI files, newest first."""
    if not _stat_dir:
        return []
    files = []
    for f in Path(_stat_dir).glob("*.ini"):
        date_str = f.stem  # "2025-11-07"
        files.append((date_str, str(f)))
    return sorted(files, key=lambda x: x[0], reverse=True)


# --- Routes (auto-dispatch based on source) ---

@router.get("/summary")
def report_summary() -> dict[str, Any]:
    if _source == "sqlite":
        return _sqlite_summary()
    elif _source == "ini":
        return _ini_summary()
    return {"source": "none", "total_jobs": 0, "message": "No history data available"}


@router.get("/recent")
def report_recent(limit: int = Query(default=20, le=100)) -> list[dict[str, Any]]:
    if _source == "sqlite":
        return _sqlite_recent(limit)
    return []  # DTG INI format doesn't track individual jobs


@router.get("/daily")
def report_daily(days: int = Query(default=30, le=365)) -> list[dict[str, Any]]:
    if _source == "sqlite":
        return _sqlite_daily(days)
    elif _source == "ini":
        return _ini_daily(days)
    return []


@router.get("/ink")
def report_ink() -> list[dict[str, Any]]:
    if _source == "sqlite":
        return _sqlite_ink()
    elif _source == "ini":
        return _ini_ink()
    return []


@router.get("/source")
def report_source() -> dict[str, str]:
    return {"source": _source, "db_path": _db_path or "", "stat_dir": _stat_dir or ""}


# --- SQLite implementations ---

def _sqlite_summary() -> dict[str, Any]:
    db = _get_db()
    cur = db.cursor()
    cur.execute("SELECT count(*) FROM TaskStatistic")
    total = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM TaskStatistic WHERE PrintedStatus=2")
    completed = cur.fetchone()[0]
    cur.execute("SELECT sum(PrintedArea), sum(PrintedTimeCost) FROM TaskStatistic WHERE PrintedStatus=2")
    row = cur.fetchone()
    cur.execute("SELECT count(DISTINCT TaskName) FROM TaskStatistic")
    unique = cur.fetchone()[0]
    cur.execute("SELECT min(StartPrintTimeTxt), max(EndPrintTimeTxt) FROM TaskStatistic")
    dates = cur.fetchone()
    cur.execute("SELECT sum(PrintInkCost) FROM TaskStatistic")
    ink = cur.fetchone()[0] or 0
    db.close()
    return {
        "source": "sqlite",
        "total_jobs": total, "completed": completed, "unique_designs": unique,
        "total_area_m2": round((row[0] or 0), 2),
        "total_time_s": row[1] or 0,
        "total_time_display": f"{(row[1] or 0) // 3600}h {((row[1] or 0) % 3600) // 60}m",
        "total_ink_cost": round(ink, 2),
        "date_from": dates[0] or "", "date_to": dates[1] or "",
    }


def _sqlite_recent(limit: int) -> list[dict[str, Any]]:
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
            "id": r[0], "name": r[1], "start": r[2] or "", "end": r[3] or "",
            "status": STATUS_MAP.get(r[4], f"?{r[4]}"), "status_code": r[4],
            "copies_total": r[5] or 0, "copies_done": r[6] or 0,
            "width_mm": round(r[7] or 0, 1), "length_mm": round(r[8] or 0, 1),
            "area_m2": round(r[9] or 0, 4), "progress": round(r[10] or 0, 1),
            "time_s": r[11] or 0, "pass_mode": r[12] or "",
            "dpi": f"{r[13] or 0}x{r[14] or 0}", "ink_cost": round(r[15] or 0, 2),
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


def _sqlite_daily(days: int) -> list[dict[str, Any]]:
    db = _get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT date(StartPrintTimeTxt) as day, count(*) as jobs,
               count(DISTINCT TaskName) as designs, sum(PrintedCopys) as copies,
               sum(PrintedArea) as area, sum(PrintedTimeCost) as time_s,
               sum(PrintInkCost) as ink
        FROM TaskStatistic WHERE PrintedStatus=2
        GROUP BY day ORDER BY day DESC LIMIT ?
    """, (days,))
    rows = [{"date": r[0], "jobs": r[1], "designs": r[2], "copies": r[3] or 0,
             "area_m2": round(r[4] or 0, 3), "time_s": r[5] or 0,
             "ink_cost": round(r[6] or 0, 2)} for r in cur.fetchall()]
    db.close()
    return rows


def _sqlite_ink() -> list[dict[str, Any]]:
    db = _get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT InkName, count(*) as jobs, sum(PrintCost) as print_cost,
               sum(FlashCost) as flash_cost
        FROM InkCostCMYK GROUP BY InkName ORDER BY print_cost DESC
    """)
    rows = [{"channel": r[0], "jobs": r[1], "print_cost": round(r[2] or 0, 2),
             "flash_cost": round(r[3] or 0, 2)} for r in cur.fetchall()]
    db.close()
    return rows


# --- INI implementations (DTG) ---

def _ini_summary() -> dict[str, Any]:
    files = _list_daily_inis()
    total_planned = 0
    total_actual = 0
    total_ink = 0.0

    for date_str, path in files:
        d = _parse_daily_ini(path)
        total_planned += d["planned"]
        total_actual += d["actual"]
        total_ink += sum(d["ink"].values())

    return {
        "source": "ini",
        "total_jobs": total_actual,
        "completed": total_actual,
        "unique_designs": 0,
        "total_area_m2": 0,
        "total_time_s": 0,
        "total_time_display": "N/A",
        "total_ink_cost": round(total_ink, 2),
        "total_planned": total_planned,
        "date_from": files[-1][0] if files else "",
        "date_to": files[0][0] if files else "",
        "days_tracked": len(files),
    }


def _ini_daily(days: int) -> list[dict[str, Any]]:
    files = _list_daily_inis()[:days]
    rows = []
    for date_str, path in files:
        d = _parse_daily_ini(path)
        ink_total = sum(d["ink"].values())
        rows.append({
            "date": date_str,
            "jobs": d["actual"],
            "designs": 0,
            "copies": d["planned"],
            "area_m2": 0,
            "time_s": 0,
            "ink_cost": round(ink_total, 2),
            "planned": d["planned"],
            "remaining": d["planned"] - d["actual"],
        })
    return rows


def _ini_ink() -> list[dict[str, Any]]:
    files = _list_daily_inis()
    totals: dict[str, float] = {}

    for _, path in files:
        d = _parse_daily_ini(path)
        for ch, amount in d["ink"].items():
            totals[ch] = totals.get(ch, 0) + amount

    return [{"channel": ch, "jobs": len(files), "print_cost": round(amt, 2), "flash_cost": 0}
            for ch, amt in sorted(totals.items(), key=lambda x: -x[1])]
