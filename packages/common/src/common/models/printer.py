"""Printer domain models — types, live status, button ID maps."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PrinterType(str, Enum):
    """Supported printer hardware families."""

    DTG = "dtg"
    DTF = "dtf"
    UV = "uv"


@dataclass
class PrinterStatus:
    """Live snapshot of a single printer's state."""

    type: PrinterType
    connected: bool = False
    printing: bool = False
    position_x: float = 0.0
    position_y: float = 0.0
    # ink_levels: channel name → percentage (0–100)
    ink_levels: dict[str, float] = field(default_factory=dict)
    current_job: Optional[str] = None  # job id or None when idle
    # MULTIWS workstation fields (DTG dual-platen only)
    active_ws: Optional[int] = None  # 0=WS:0 (left), 1=WS:1 (right)
    ws0_busy: bool = False
    ws1_busy: bool = False

    def is_idle(self) -> bool:
        return self.connected and not self.printing and self.current_job is None


@dataclass
class ButtonIDs:
    """WM_COMMAND control IDs grouped by printer type.

    Values sourced from PrintExp resource analysis.
    Each dict maps a logical action name to its HMENU integer control ID.
    """

    # --- DTG button map (PrintExp standard layout) ---
    DTG_BUTTONS: dict[str, int] = field(
        default_factory=lambda: {
            "move_left": 0x8004,
            "move_right": 0x8005,
            "move_ahead": 0x8006,
            "move_back": 0x8007,
            "print_start": 0x8001,
            "pause": 0x8002,
            "cancel": 0x8003,
            "home_x": 0x8008,
            "home_y": 0x8009,
            "clean": 0x800A,
            "flash": 0x800B,
        }
    )

    # --- DTF button map (shares most IDs with DTG, overrides where different) ---
    DTF_BUTTONS: dict[str, int] = field(
        default_factory=lambda: {
            "move_left": 0x8004,
            "move_right": 0x8005,
            "move_ahead": 0x8006,
            "move_back": 0x8007,
            "print_start": 0x8001,
            "pause": 0x8002,
            "cancel": 0x8003,
            "home_x": 0x8008,
            "home_y": 0x8009,
            "clean": 0x800C,  # DTF uses different clean control
            "flash": 0x800D,
            "heat_on": 0x800E,
            "heat_off": 0x800F,
        }
    )

    # --- UV flatbed button map ---
    UV_BUTTONS: dict[str, int] = field(
        default_factory=lambda: {
            "move_left": 0x8014,
            "move_right": 0x8015,
            "move_ahead": 0x8016,
            "move_back": 0x8017,
            "print_start": 0x8011,
            "pause": 0x8012,
            "cancel": 0x8013,
            "home_x": 0x8018,
            "home_y": 0x8019,
            "home_z": 0x801A,
            "clean": 0x801B,
            "flash": 0x801C,
            "uv_on": 0x801D,
            "uv_off": 0x801E,
        }
    )

    def get_map(self, printer_type: PrinterType) -> dict[str, int]:
        """Return the button map for the given printer type."""
        maps = {
            PrinterType.DTG: self.DTG_BUTTONS,
            PrinterType.DTF: self.DTF_BUTTONS,
            PrinterType.UV: self.UV_BUTTONS,
        }
        return maps[printer_type]
