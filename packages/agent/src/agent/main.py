"""Agent entry point — CLI with argparse, auto-detect printer type, start API server."""

from __future__ import annotations

import argparse
import sys

import uvicorn

from common.config import AgentConfig
from common.models.printer import PrinterType
from agent.api import app, set_backend
from agent.printer.mock import MockBackend
from agent.printer.dtg import DTGBackend
from agent.printexp.detector import detect_printer_type


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


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    # Load config (falls back to defaults if file missing)
    config = AgentConfig.load(args.config)

    # Override port from CLI if given
    if args.port != 8080 or config.port == 8080:
        config.port = args.port

    # Resolve printer type
    if args.mock:
        printer_type = PrinterType.DTG
    elif args.printer_type != "auto":
        printer_type = PrinterType(args.printer_type)
    else:
        printer_type = detect_printer_type(config.printexp_path)

    # Build backend
    if args.mock:
        backend = MockBackend(printer_type=printer_type)
        print(f"[agent] Mock mode — printer type: {printer_type.value}", flush=True)
    else:
        if sys.platform != "win32":
            print("[agent] WARNING: DTGBackend requires Windows. Falling back to MockBackend.", flush=True)
            backend = MockBackend(printer_type=printer_type)
        else:
            config.printer_type = printer_type.value
            backend = DTGBackend(config)
            print(f"[agent] Real mode — printer type: {printer_type.value}", flush=True)

    set_backend(backend)

    print(f"[agent] Starting on {args.host}:{config.port}", flush=True)
    uvicorn.run(app, host=args.host, port=config.port, log_level="info")


if __name__ == "__main__":
    main()
