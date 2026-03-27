"""Parse PrintExp MULTIWS log patterns to determine workstation state.

PrintExp writes Chinese log lines indicating WS activity:
  [ThreadWorkstation] 工位(0) 启动线程   — WS:0 thread started (printing)
  [ThreadWorkstation] 工位(1) 启动线程   — WS:1 thread started (printing)
  [_JobProcessCloseWS]工位(0)已经打印完毕 — WS:0 finished printing
  [_JobProcessCloseWS]工位(1)已经打印完毕 — WS:1 finished printing

Log files are GBK-encoded, located at: {printexp_path}/Log/YYYYMMDD.log
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

# Patterns for WS thread start (= busy) and close (= idle)
_WS_START = re.compile(r"\[ThreadWorkstation\]\s*工位\((\d+)\)\s*启动")
_WS_CLOSE = re.compile(r"\[_JobProcessCloseWS\]工位\((\d+)\)已经打印完毕")

# How many lines from end of log to scan (avoid reading entire multi-MB log)
_TAIL_LINES = 200


def parse_ws_state(printexp_path: str) -> dict:
    """Read today's PrintExp log tail and determine WS:0/WS:1 busy state.

    Returns dict with keys: active_ws, ws0_busy, ws1_busy, printing.
    """
    log_dir = Path(printexp_path) / "Log"
    today_log = log_dir / f"{date.today().strftime('%Y%m%d')}.log"

    if not today_log.exists():
        return {"active_ws": None, "ws0_busy": False, "ws1_busy": False, "printing": False}

    # Read last N lines (GBK encoded, common for Chinese PrintExp)
    lines = _read_tail(today_log, _TAIL_LINES)

    # Track latest event per WS: True = started (busy), False = closed (idle)
    ws_state = {0: False, 1: False}
    active_ws = None

    for line in lines:
        m_start = _WS_START.search(line)
        if m_start:
            ws_idx = int(m_start.group(1))
            if ws_idx in ws_state:
                ws_state[ws_idx] = True
                active_ws = ws_idx

        m_close = _WS_CLOSE.search(line)
        if m_close:
            ws_idx = int(m_close.group(1))
            if ws_idx in ws_state:
                ws_state[ws_idx] = False

    any_busy = ws_state[0] or ws_state[1]
    return {
        "active_ws": active_ws if any_busy else None,
        "ws0_busy": ws_state[0],
        "ws1_busy": ws_state[1],
        "printing": any_busy,
    }


def _read_tail(filepath: Path, n_lines: int) -> list[str]:
    """Read last n_lines from a GBK-encoded file."""
    try:
        with filepath.open("r", encoding="gbk", errors="replace") as f:
            all_lines = f.readlines()
        return all_lines[-n_lines:]
    except Exception:
        return []
