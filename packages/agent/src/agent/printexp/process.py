"""PrintExp process management — find, start, check running state."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional


def find_printexp_pid() -> Optional[int]:
    """Scan running processes and return the PID of PrintExp, or None.

    Uses CreateToolhelp32Snapshot on Windows.
    Returns None on non-Windows or if process not found.
    """
    if sys.platform != "win32":
        return None

    try:
        import ctypes
        import ctypes.wintypes as wt

        TH32CS_SNAPPROCESS = 0x00000002

        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize", wt.DWORD),
                ("cntUsage", wt.DWORD),
                ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD),
                ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_char * 260),
            ]

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == ctypes.c_void_p(-1).value:
            return None

        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)

        try:
            if not kernel32.Process32First(snap, ctypes.byref(entry)):
                return None
            while True:
                name = entry.szExeFile.decode("ascii", errors="replace").lower()
                if "printexp" in name:
                    return int(entry.th32ProcessID)
                if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                    break
        finally:
            kernel32.CloseHandle(snap)

    except Exception:
        pass

    return None


def is_running() -> bool:
    """Return True if PrintExp is currently running."""
    return find_printexp_pid() is not None


def start_printexp(exe_path: str | Path) -> int:
    """Launch PrintExp and return the new process PID.

    Args:
        exe_path: Full path to PrintExp.exe.

    Returns:
        PID of the spawned process.

    Raises:
        FileNotFoundError: If the exe does not exist.
        OSError: If the process cannot be started.
    """
    path = Path(exe_path)
    if not path.exists():
        raise FileNotFoundError(f"PrintExp executable not found: {path}")

    proc = subprocess.Popen(
        [str(path)],
        cwd=str(path.parent),
        # Detach from our process group so it persists if agent restarts
        creationflags=0x00000008 if sys.platform == "win32" else 0,  # DETACHED_PROCESS
    )
    return proc.pid
