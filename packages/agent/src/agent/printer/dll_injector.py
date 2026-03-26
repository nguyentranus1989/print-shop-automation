"""One-time DLL injector for PrintFlow Bridge.

Injects printflow-bridge.dll into PrintExp_X64.exe via CreateRemoteThread.
Only needs to run once — the DLL stays resident and serves commands via named pipe.
"""

import ctypes
import ctypes.wintypes as wt
import os
import time

from .bridge_client import BridgeClient

k32 = ctypes.windll.kernel32
k32.GetModuleHandleA.restype = wt.HMODULE
k32.GetModuleHandleA.argtypes = [ctypes.c_char_p]
k32.GetProcAddress.restype = ctypes.c_void_p
k32.GetProcAddress.argtypes = [wt.HMODULE, ctypes.c_char_p]
k32.OpenProcess.restype = wt.HANDLE
k32.VirtualAllocEx.restype = ctypes.c_void_p
k32.CreateRemoteThread.restype = wt.HANDLE


def find_printexp_pid() -> int | None:
    """Find PrintExp_X64.exe PID using Win32 API."""
    from .win32_process_helpers import find_process_pid
    return find_process_pid("PrintExp_X64")


def inject_dll(pid: int, dll_path: str) -> bool:
    """Inject DLL into target process via CreateRemoteThread + LoadLibraryA."""
    PROCESS_ALL_ACCESS = 0x001F0FFF

    h_process = k32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not h_process:
        return False

    try:
        dll_bytes = dll_path.encode("ascii") + b"\x00"
        remote_mem = k32.VirtualAllocEx(h_process, None, len(dll_bytes), 0x3000, 0x40)
        if not remote_mem:
            return False

        k32.WriteProcessMemory(
            h_process, ctypes.c_void_p(remote_mem),
            dll_bytes, len(dll_bytes), None,
        )

        load_lib = k32.GetProcAddress(
            k32.GetModuleHandleA(b"kernel32.dll"), b"LoadLibraryA",
        )
        h_thread = k32.CreateRemoteThread(
            h_process, None, 0,
            ctypes.c_void_p(load_lib),
            ctypes.c_void_p(remote_mem),
            0, None,
        )
        if not h_thread:
            return False

        k32.WaitForSingleObject(h_thread, 10000)
        exit_code = wt.DWORD(0)
        k32.GetExitCodeThread(h_thread, ctypes.byref(exit_code))
        k32.CloseHandle(h_thread)
        k32.VirtualFreeEx(h_process, ctypes.c_void_p(remote_mem), 0, 0x8000)

        return exit_code.value != 0

    finally:
        k32.CloseHandle(h_process)


def ensure_bridge(dll_path: str, max_retries: int = 3) -> BridgeClient:
    """Ensure bridge DLL is injected and pipe is responding.

    Returns a connected BridgeClient, or raises RuntimeError.
    """
    client = BridgeClient()

    # Already connected?
    if client.is_connected():
        return client

    # Find PrintExp
    pid = find_printexp_pid()
    if not pid:
        raise RuntimeError("PrintExp_X64.exe not running")

    # Inject
    if not os.path.exists(dll_path):
        raise RuntimeError(f"Bridge DLL not found: {dll_path}")

    for attempt in range(max_retries):
        if inject_dll(pid, dll_path):
            # Wait for pipe to become available
            for _ in range(10):
                time.sleep(0.5)
                if client.is_connected():
                    return client
            # Pipe didn't appear — DLL loaded but pipe failed?
            raise RuntimeError("DLL injected but pipe not responding")

        time.sleep(1)

    raise RuntimeError(f"DLL injection failed after {max_retries} attempts (run as admin?)")
