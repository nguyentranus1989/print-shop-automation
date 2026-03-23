"""Win32 window enumeration helpers for WM_COMMAND dispatch.

Extracted from wm_command.py to keep it under 200 lines.
All functions return None / False on non-Windows or any Win32 error.
"""

from __future__ import annotations

import sys
from typing import Optional


def load_user32() -> tuple[object, object] | tuple[None, None]:
    """Load user32.dll and return (EnumWindowsProc type, user32 module).

    Returns (None, None) on non-Windows or import failure.
    """
    if sys.platform != "win32":
        return None, None
    try:
        import ctypes
        import ctypes.wintypes as wt

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]

        EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)  # type: ignore[attr-defined]
        user32.EnumWindows.argtypes = [EnumWindowsProc, wt.LPARAM]
        user32.EnumWindows.restype = wt.BOOL

        user32.GetWindowTextW.argtypes = [wt.HWND, ctypes.c_wchar_p, ctypes.c_int]
        user32.GetWindowTextW.restype = ctypes.c_int

        user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
        user32.PostMessageW.restype = wt.BOOL

        return EnumWindowsProc, user32
    except Exception:
        return None, None


def find_window_by_title_fragment(title_fragment: str) -> Optional[int]:
    """Enumerate top-level windows and return HWND of the first match.

    Args:
        title_fragment: Substring to search for in window title text.

    Returns:
        HWND integer, or None if not found / not on Windows.
    """
    EnumWindowsProc, user32 = load_user32()
    if user32 is None or EnumWindowsProc is None:
        return None

    try:
        import ctypes

        # Window classes to ignore (File Explorer, browser tabs, etc.)
        _IGNORE_CLASSES = {"CabinetWClass", "ExploreWClass", "Chrome_WidgetWin_1",
                           "MozillaWindowClass", "ApplicationFrameWindow"}

        found: list[int] = []

        def callback(hwnd: int, _lparam: int) -> bool:
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if title_fragment in buf.value:
                # Check window class to filter out Explorer/browser windows
                cls_buf = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, cls_buf, 256)
                if cls_buf.value not in _IGNORE_CLASSES:
                    found.append(hwnd)
                    return False  # stop enumeration
            return True

        user32.EnumWindows(EnumWindowsProc(callback), 0)
        return found[0] if found else None
    except Exception:
        return None


def post_message(hwnd: int, msg: int, wparam: int, lparam: int) -> bool:
    """Call PostMessageW(hwnd, msg, wparam, lparam).

    Returns True on success, False on failure or non-Windows.
    """
    _, user32 = load_user32()
    if user32 is None:
        return False
    try:
        result = user32.PostMessageW(hwnd, msg, wparam, lparam)
        return bool(result)
    except Exception:
        return False
