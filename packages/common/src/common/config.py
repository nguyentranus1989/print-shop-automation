"""Agent configuration loader.

Reads agent.toml using tomllib (stdlib, Python 3.11+).
Falls back gracefully if file is missing (useful for tests/mock mode).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class AgentConfig:
    """Runtime configuration for a single printer agent."""

    # Printer hardware
    printer_type: str = "auto"            # "auto" | "dtg" | "dtf" | "uv"
    printexp_path: str = r"C:\PrintExp"   # path to PrintExp installation

    # Network
    port: int = 8080                      # agent HTTP API port
    dashboard_url: str = "http://localhost:8000"

    # Filesystem
    nas_path: str = r"\\nas\prn-files"   # UNC or local path for .prn files
    temp_path: str = r"C:\Hstemp"        # local temp for downloaded files

    # Agent identity
    name: str = "PrintFlow-Agent"
    poll_interval_seconds: int = 5

    # PrintExp TCP
    tcp_port: int = 9100
    memory_offset: int = 0x016CDB        # DeviceManager.dll filename patch offset

    @classmethod
    def load(cls, config_path: str | Path = "agent.toml") -> "AgentConfig":
        """Load config from a TOML file.

        Missing keys fall back to dataclass defaults.
        Missing file returns default config (useful for --mock mode).
        """
        path = Path(config_path)
        if not path.exists():
            return cls()

        with path.open("rb") as fh:
            raw = tomllib.load(fh)

        printer_section = raw.get("printer", {})
        network_section = raw.get("network", {})
        files_section = raw.get("files", {})
        agent_section = raw.get("agent", {})
        printexp_section = raw.get("printexp", {})

        return cls(
            printer_type=printer_section.get("type", "auto"),
            printexp_path=printexp_section.get("exe_path", r"C:\PrintExp"),
            port=network_section.get("port", 8080),
            dashboard_url=network_section.get("dashboard_url", "http://localhost:8000"),
            nas_path=files_section.get("nas_path", r"\\nas\prn-files"),
            temp_path=files_section.get("temp_path", r"C:\Hstemp"),
            name=agent_section.get("name", "PrintFlow-Agent"),
            poll_interval_seconds=agent_section.get("poll_interval_seconds", 5),
            tcp_port=printexp_section.get("tcp_port", 9100),
            memory_offset=printexp_section.get("memory_offset", 0x016CDB),
        )
