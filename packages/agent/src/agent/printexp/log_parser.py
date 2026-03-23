"""PrintExp log file parser.

PrintExp writes GBK-encoded log files.  This module extracts structured
events from those logs: connection status, print events, ink stats, errors.

Log line format (typical):
    2024-03-15 14:22:01 [INFO] PrintTask: job=rip.prn status=done pages=1
    2024-03-15 14:22:01 [ERROR] TCP: connection refused port=9100
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class LogEvent:
    """A single parsed log entry."""

    timestamp: Optional[datetime]
    level: str          # INFO, WARN, ERROR, DEBUG
    category: str       # TCP, PrintTask, Ink, System, etc.
    message: str
    raw: str            # original line for debugging


@dataclass
class ParsedLog:
    """Aggregated result from parsing a log file."""

    events: list[LogEvent] = field(default_factory=list)
    connection_events: list[LogEvent] = field(default_factory=list)
    print_events: list[LogEvent] = field(default_factory=list)
    ink_events: list[LogEvent] = field(default_factory=list)
    errors: list[LogEvent] = field(default_factory=list)


# Regex patterns for log line structure
_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"\[(?P<level>\w+)\]\s+"
    r"(?P<category>\w+):\s+"
    r"(?P<message>.+)$"
)

_TS_FMT = "%Y-%m-%d %H:%M:%S"

# Categories that map to connection events
_CONNECTION_CATEGORIES = {"tcp", "connection", "socket", "network"}
_PRINT_CATEGORIES = {"printtask", "print", "job", "rip"}
_INK_CATEGORIES = {"ink", "inkstats", "cartridge"}


def parse_log_file(log_path: str | Path) -> ParsedLog:
    """Parse a GBK-encoded PrintExp log file.

    Args:
        log_path: Path to the log file.

    Returns:
        ParsedLog with all events classified.

    Raises:
        FileNotFoundError: If log_path does not exist.
    """
    path = Path(log_path)
    if not path.exists():
        raise FileNotFoundError(f"Log file not found: {path}")

    result = ParsedLog()

    # GBK encoding is standard for Chinese Windows software
    with path.open("r", encoding="gbk", errors="replace") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n\r")
            if not line.strip():
                continue

            event = _parse_line(line)
            result.events.append(event)
            _classify(event, result)

    return result


def _parse_line(raw: str) -> LogEvent:
    """Parse a single log line into a LogEvent."""
    match = _LINE_RE.match(raw)
    if not match:
        return LogEvent(
            timestamp=None,
            level="UNKNOWN",
            category="raw",
            message=raw,
            raw=raw,
        )

    ts_str = match.group("ts")
    try:
        ts = datetime.strptime(ts_str, _TS_FMT)
    except ValueError:
        ts = None

    return LogEvent(
        timestamp=ts,
        level=match.group("level").upper(),
        category=match.group("category"),
        message=match.group("message"),
        raw=raw,
    )


def _classify(event: LogEvent, result: ParsedLog) -> None:
    """Route event into the appropriate bucket in ParsedLog."""
    cat = event.category.lower()

    if cat in _CONNECTION_CATEGORIES:
        result.connection_events.append(event)
    elif cat in _PRINT_CATEGORIES:
        result.print_events.append(event)
    elif cat in _INK_CATEGORIES:
        result.ink_events.append(event)

    if event.level in ("ERROR", "CRITICAL", "FATAL"):
        result.errors.append(event)
