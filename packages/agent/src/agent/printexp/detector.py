"""Detect which PrintExp printer type is installed on this workstation.

Detection strategy (in priority order):
  1. Process name contains a printer type hint (e.g. "PrintExp_DTF")
  2. Project.ini in the PrintExp directory contains a type key
  3. Presence of type-specific DLLs in the installation directory
  4. Fall back to DTG (most common)
"""

from __future__ import annotations

import configparser
import sys
from pathlib import Path
from typing import Optional

from common.models.printer import PrinterType


def detect_printer_type(printexp_path: str | Path | None = None) -> PrinterType:
    """Attempt to determine the PrinterType from the local installation.

    Args:
        printexp_path: Path to the PrintExp installation directory.
                       If None, common paths are searched.

    Returns:
        Detected PrinterType, defaulting to DTG if unknown.
    """
    # 1. Check running process name
    detected = _detect_from_process()
    if detected:
        return detected

    # 2. Check Project.ini
    search_paths = _resolve_search_paths(printexp_path)
    detected = _detect_from_ini(search_paths)
    if detected:
        return detected

    # 3. Check DLL presence
    detected = _detect_from_dlls(search_paths)
    if detected:
        return detected

    # 4. Default
    return PrinterType.DTG


def _detect_from_process() -> Optional[PrinterType]:
    """Check if a running process name hints at the printer type."""
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
                # Only match PrintExp processes, not unrelated tools like uv.exe
                if "printexp" not in name:
                    if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                        break
                    continue
                if "dtf" in name:
                    return PrinterType.DTF
                if "uv" in name:
                    return PrinterType.UV
                return PrinterType.DTG  # default when process found but type unknown
        finally:
            kernel32.CloseHandle(snap)
    except Exception:
        pass

    return None


def _detect_from_ini(paths: list[Path]) -> Optional[PrinterType]:
    """Read Project.ini for a [Printer] Type key."""
    for base in paths:
        ini_path = base / "Project.ini"
        if not ini_path.exists():
            continue

        config = configparser.ConfigParser()
        try:
            config.read(str(ini_path), encoding="utf-8")
        except Exception:
            continue

        type_str = config.get("Printer", "Type", fallback="").lower()
        if "dtf" in type_str:
            return PrinterType.DTF
        if "uv" in type_str:
            return PrinterType.UV
        if "dtg" in type_str or type_str:
            return PrinterType.DTG

    return None


def _detect_from_dlls(paths: list[Path]) -> Optional[PrinterType]:
    """Look for type-specific DLLs in the installation directory."""
    dtf_hints = {"dtfdevice.dll", "dtf_core.dll"}
    uv_hints = {"uvdevice.dll", "uv_flatbed.dll"}

    for base in paths:
        if not base.exists():
            continue
        dlls = {p.name.lower() for p in base.glob("*.dll")}
        if dlls & dtf_hints:
            return PrinterType.DTF
        if dlls & uv_hints:
            return PrinterType.UV

    return None


def _resolve_search_paths(printexp_path: str | Path | None) -> list[Path]:
    """Build list of directories to search for PrintExp files."""
    paths: list[Path] = []
    if printexp_path:
        paths.append(Path(printexp_path))

    # Common default installation locations
    defaults = [
        Path(r"C:\PrintExp_5.7.7.1.12_MULTIWS"),
        Path(r"C:\PrintExp"),
        Path(r"D:\PrintExp"),
    ]
    paths.extend(defaults)
    return paths
