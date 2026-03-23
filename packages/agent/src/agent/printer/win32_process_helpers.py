"""Win32 process and module enumeration helpers (ctypes only, no pywin32).

Extracted into a separate module to keep dtg.py under 200 lines.
All functions return None on non-Windows or on any Win32 error.
"""

from __future__ import annotations

import ctypes
import sys
from typing import Optional


def find_process_pid(exe_name_fragment: str) -> Optional[int]:
    """Scan running processes and return PID where exe name contains the fragment."""
    if sys.platform != "win32":
        return None

    try:
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
                if exe_name_fragment.lower() in name:
                    return int(entry.th32ProcessID)
                if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                    break
        finally:
            kernel32.CloseHandle(snap)
    except Exception:
        pass

    return None


def get_module_base_address(pid: int, dll_name: str) -> Optional[int]:
    """Return base address of a loaded DLL in the target process."""
    if sys.platform != "win32":
        return None

    try:
        import ctypes.wintypes as wt

        TH32CS_SNAPMODULE = 0x00000008

        class MODULEENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize", wt.DWORD),
                ("th32ModuleID", wt.DWORD),
                ("th32ProcessID", wt.DWORD),
                ("GlblcntUsage", wt.DWORD),
                ("ProccntUsage", wt.DWORD),
                ("modBaseAddr", ctypes.POINTER(wt.BYTE)),
                ("modBaseSize", wt.DWORD),
                ("hModule", wt.HMODULE),
                ("szModule", ctypes.c_char * 256),
                ("szExePath", ctypes.c_char * 260),
            ]

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, pid)
        if snap == ctypes.c_void_p(-1).value:
            return None

        entry = MODULEENTRY32()
        entry.dwSize = ctypes.sizeof(MODULEENTRY32)

        try:
            if not kernel32.Module32First(snap, ctypes.byref(entry)):
                return None
            while True:
                name = entry.szModule.decode("ascii", errors="replace").lower()
                if dll_name.lower() in name:
                    return ctypes.cast(entry.modBaseAddr, ctypes.c_void_p).value
                if not kernel32.Module32Next(snap, ctypes.byref(entry)):
                    break
        finally:
            kernel32.CloseHandle(snap)
    except Exception:
        pass

    return None


def write_process_memory(pid: int, address: int, data: bytes) -> bool:
    """Write bytes into a process's virtual memory via WriteProcessMemory."""
    if sys.platform != "win32":
        return False

    _PROCESS_VM_WRITE = 0x0020
    _PROCESS_VM_OPERATION = 0x0008

    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(_PROCESS_VM_WRITE | _PROCESS_VM_OPERATION, False, pid)
        if not handle:
            return False
        try:
            buf = ctypes.create_string_buffer(data)
            written = ctypes.c_size_t(0)
            ok = kernel32.WriteProcessMemory(
                handle,
                ctypes.c_void_p(address),
                buf,
                len(data),
                ctypes.byref(written),
            )
            return bool(ok)
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return False
