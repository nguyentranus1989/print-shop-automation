"""WM_COMMAND controller — sends button commands to PrintExp via Win32 PostMessage.

Uses ctypes to call Win32 APIs with zero third-party dependencies.
Win32 window helpers are in win32_window_helpers.py.
On non-Windows platforms (e.g. CI), all calls return False gracefully.
"""

from __future__ import annotations

from typing import Optional

from common.protocols.win32_window_helpers import find_window_by_title_fragment, post_message

# --- Button ID constants --------------------------------------------------

# DTG printer WM_COMMAND control IDs
DTG_BUTTONS: dict[str, int] = {
    "move_left": 1350,
    "move_right": 1351,
    "move_ahead": 1283,
    "move_back": 1284,
    "print_start": 11026,
    "pause": 11027,
    "cancel": 11028,
    "check": 11029,
    "home_x": 11037,
    "home_y": 11049,
    "clean": 1201,
    "flash": 11042,
    "keep_wet": 11043,
    "step_minus": 11038,
    "step_plus": 11039,
}

# DTF — different IDs from DTG (64-bit build)
DTF_BUTTONS: dict[str, int] = {
    "move_left": 11033,
    "move_right": 11034,
    "move_ahead": 11035,
    "move_back": 11036,
    "print_start": 4,
    "open_files": 5,
    "pause": 11027,
    "cancel": 11028,
    "check": 11029,
    "home_x": 11037,
    "home_y": 11049,
    "clean": 11030,
    "flash": 11042,
    "keep_wet": 11043,
    "step_minus": 11038,
    "step_plus": 11039,
}

# UV flatbed — different movement IDs (Chinese labels)
UV_BUTTONS: dict[str, int] = {
    "move_left": 2228,
    "move_right": 2225,
    "move_ahead": 2226,
    "move_back": 2227,
    "print_start": 1104,
    "pause": 11027,
    "cancel": 1026,
    "check": 11029,
    "home_x": 11037,
    "home_y": 11049,
    "clean": 11030,
    "flash": 11042,
    "keep_wet": 11043,
    "z_up": 11056,
    "z_down": 11055,
    "z_axis": 11048,
    "uv_on": 0x801D,
    "uv_off": 0x801E,
}

WM_COMMAND = 0x0111


# --- Controller -----------------------------------------------------------

class WMCommandController:
    """Send WM_COMMAND messages to the PrintExp window.

    Finds the PrintExp HWND by window title each time (it changes on restart),
    then posts button messages without needing focus.

    Usage::

        ctrl = WMCommandController(buttons=DTG_BUTTONS)
        ctrl.print_start()
        ctrl.move_left()
    """

    def __init__(self, buttons: dict[str, int] | None = None) -> None:
        # Default to DTG button map
        self.buttons = buttons or DTG_BUTTONS
        self._hwnd: Optional[int] = None

    # ------------------------------------------------------------------
    # Window discovery
    # ------------------------------------------------------------------

    def find_printexp_window(self) -> Optional[int]:
        """Enumerate top-level windows and return HWND of the PrintExp window."""
        self._hwnd = find_window_by_title_fragment("PrintExp")
        return self._hwnd

    # ------------------------------------------------------------------
    # Low-level dispatch
    # ------------------------------------------------------------------

    def send_command(self, ctrl_id: int) -> bool:
        """Post a WM_COMMAND message to the PrintExp window."""
        hwnd = self._hwnd or self.find_printexp_window()
        if hwnd is None:
            return False
        return post_message(hwnd, WM_COMMAND, ctrl_id, 0)

    def send_named(self, action: str) -> bool:
        """Send a command by action name (must exist in self.buttons)."""
        ctrl_id = self.buttons.get(action)
        if ctrl_id is None:
            raise KeyError(f"Unknown action '{action}' for current button map")
        return self.send_command(ctrl_id)

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def move_left(self) -> bool:
        return self.send_named("move_left")

    def move_right(self) -> bool:
        return self.send_named("move_right")

    def move_ahead(self) -> bool:
        return self.send_named("move_ahead")

    def move_back(self) -> bool:
        return self.send_named("move_back")

    def print_start(self) -> bool:
        return self.send_named("print_start")

    def pause(self) -> bool:
        return self.send_named("pause")

    def cancel(self) -> bool:
        return self.send_named("cancel")

    def home_x(self) -> bool:
        return self.send_named("home_x")

    def home_y(self) -> bool:
        return self.send_named("home_y")

    def clean(self) -> bool:
        return self.send_named("clean")

    def flash(self) -> bool:
        return self.send_named("flash")
