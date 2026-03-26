"""Agent entry point — CLI with argparse, auto-detect printer type, start API server."""

from __future__ import annotations

import argparse
import asyncio
import sys

import uvicorn

from common.config import AgentConfig
from common.models.printer import PrinterType
from agent.api import app, set_backend, set_printer_info
from agent.printer.mock import MockBackend
from agent.printer.dtg import DTGBackend
from agent.printer.dtf import DTFBackend
from agent.printexp.detector import detect_printer_type
from agent.registration import register_with_dashboard, heartbeat_loop
from agent.job_dispatch import job_dispatch_loop


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="printflow-agent",
        description="PrintFlow printer agent — inject jobs, report status.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=False,
        help="Use mock backend (no real printer required)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="HTTP API port (default: 8080)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="agent.toml",
        help="Path to agent.toml config file (default: agent.toml)",
    )
    parser.add_argument(
        "--printer-type",
        choices=["auto", "dtg", "dtf", "uv"],
        default="auto",
        help="Override printer type detection (default: auto)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Bind host (default: 0.0.0.0)",
    )
    return parser


def _find_config(cli_path: str) -> str:
    """Find agent.toml — check CWD, then exe directory, then exe/agent/ subdir."""
    from pathlib import Path

    candidates = [
        Path(cli_path),                                    # CWD / explicit path
        Path(sys.executable).parent / "agent.toml",        # next to exe
        Path(sys.executable).parent.parent / "agent.toml", # parent of exe dir
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return cli_path  # fallback to default (will use defaults if missing)


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    # Load config — search multiple locations
    config_path = _find_config(args.config)
    config = AgentConfig.load(config_path)
    print(f"[agent] Config: {config_path} (dashboard: {config.dashboard_url})", flush=True)

    # Override port from CLI if given
    if args.port != 8080 or config.port == 8080:
        config.port = args.port

    # Resolve printer type
    if args.mock:
        printer_type = PrinterType.DTG
    elif args.printer_type != "auto":
        printer_type = PrinterType(args.printer_type)
    elif config.printer_type and config.printer_type != "auto":
        # Config file explicitly sets type — use it, skip auto-detection
        printer_type = PrinterType(config.printer_type)
        print(f"[agent] Printer type from config: {printer_type.value}", flush=True)
    else:
        printer_type = detect_printer_type(config.printexp_path)

    # Build backend
    if args.mock:
        backend = MockBackend(printer_type=printer_type)
        print(f"[agent] Mock mode — printer type: {printer_type.value}", flush=True)
    else:
        if sys.platform != "win32":
            print("[agent] WARNING: Real backends require Windows. Falling back to MockBackend.", flush=True)
            backend = MockBackend(printer_type=printer_type)
        else:
            config.printer_type = printer_type.value
            if printer_type == PrinterType.DTF:
                backend = DTFBackend(printexp_exe=config.printexp_path)
                print(f"[agent] Real mode — DTF (DLL injection)", flush=True)
            else:
                backend = DTGBackend(config)
                print(f"[agent] Real mode — {printer_type.value} (TCP 9100)", flush=True)

    set_backend(backend)
    set_printer_info(name=config.name, printer_type=printer_type.value)

    # Configure UV report DB if PrintExp path is set
    if config.printexp_path:
        from agent.reports import set_db_path
        set_db_path(config.printexp_path)

    # Auto-register with dashboard after server starts
    _reg_config = {
        "dashboard_url": config.dashboard_url,
        "name": config.name,
        "port": config.port,
        "printer_type": printer_type.value,
    }

    @app.on_event("startup")
    async def _auto_register() -> None:
        """Register this agent and start heartbeat loop."""
        asyncio.create_task(
            register_with_dashboard(
                dashboard_url=_reg_config["dashboard_url"],
                agent_name=_reg_config["name"],
                agent_port=_reg_config["port"],
                printer_type=_reg_config["printer_type"],
            )
        )
        asyncio.create_task(
            heartbeat_loop(
                dashboard_url=_reg_config["dashboard_url"],
                agent_port=_reg_config["port"],
                printer_type=_reg_config["printer_type"],
                get_status_fn=backend.get_status,
                interval=10.0,
            )
        )
        asyncio.create_task(
            job_dispatch_loop(
                dashboard_url=_reg_config["dashboard_url"],
                printer_type=_reg_config["printer_type"],
                inject_fn=backend.inject_job,
                interval=2.0,
            )
        )

    print(f"[agent] Starting on {args.host}:{config.port}", flush=True)
    uvicorn.run(app, host=args.host, port=config.port, log_level="info")


if __name__ == "__main__":
    main()
