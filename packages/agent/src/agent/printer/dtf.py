"""DTF printer backend — DLL injection + named pipe vtable control.

Job injection: single-shot DLL (inject_config.txt -> AddFile + 0x7F4).
Control: Named pipe to persistent PrintFlow Control DLL (vtable calls),
         falls back to WM_COMMAND if pipe not available.

Target: PrintExp DTF v5.7.6.5.103, UV v5.7.9, DTF v5.8.2 (all x64)
"""

import asyncio
import logging
import os
import time

from common.models.printer import PrinterStatus, PrinterType
from common.protocols.wm_command import DTF_BUTTONS, WMCommandController
from agent.printer.named_pipe_client import NamedPipeClient

logger = logging.getLogger(__name__)


def _find_dll_dir() -> str:
    """Find the dll/ directory relative to the agent package."""
    # Check multiple locations
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "dll"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dll"),
        os.path.join(os.getcwd(), "dll"),
    ]
    for c in candidates:
        c = os.path.normpath(c)
        if os.path.isdir(c):
            return c
    return os.path.join(os.getcwd(), "dll")


class DTFBackend:
    """DTF/UV printer backend using DLL injection.

    Works for DTF and UV builds — pass button_map to select control IDs.
    """

    def __init__(self, dll_dir: str | None = None, printexp_exe: str | None = None,
                 button_map: dict[str, int] | None = None):
        self.dll_dir = dll_dir or _find_dll_dir()
        self.inject_dll = os.path.join(self.dll_dir, "printflow-bridge.dll")
        self.config_path = os.path.join(self.dll_dir, "inject_config.txt")
        self.log_path = os.path.join(self.dll_dir, "inject_log.txt")
        self.printexp_exe = printexp_exe
        self._printexp_connected = False
        self._wm = WMCommandController(buttons=button_map or DTF_BUTTONS)
        self._pipe = NamedPipeClient()

    def _find_pid(self) -> int | None:
        """Find PrintExp_X64.exe PID."""
        try:
            from .win32_process_helpers import find_process_pid
            return find_process_pid("PrintExp_X64")
        except Exception:
            return None

    def _ensure_printexp_running(self) -> int | None:
        """Start PrintExp if not running. Returns PID."""
        import subprocess

        pid = self._find_pid()
        if pid:
            return pid

        # Try to start PrintExp
        exe = self.printexp_exe
        if not exe or not os.path.exists(exe):
            logger.error("PrintExp not running and no exe path configured")
            return None

        logger.info("Starting PrintExp: %s", exe)
        exe_dir = os.path.dirname(exe)
        subprocess.Popen([exe], cwd=exe_dir)

        # Wait for it to start (up to 15 seconds)
        for _ in range(30):
            time.sleep(0.5)
            pid = self._find_pid()
            if pid:
                logger.info("PrintExp started (PID %d), waiting for init...", pid)
                time.sleep(3)  # Give it time to fully initialize
                return pid

        logger.error("PrintExp failed to start within 15 seconds")
        return None

    def _inject_dll(self, pid: int, dll_path: str) -> bool:
        """Inject DLL via CreateRemoteThread + LoadLibraryA."""
        import ctypes
        import ctypes.wintypes as wt

        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = wt.HANDLE
        k32.VirtualAllocEx.restype = ctypes.c_void_p
        k32.GetModuleHandleA.restype = wt.HMODULE
        k32.GetModuleHandleA.argtypes = [ctypes.c_char_p]
        k32.GetProcAddress.restype = ctypes.c_void_p
        k32.GetProcAddress.argtypes = [wt.HMODULE, ctypes.c_char_p]
        k32.CreateRemoteThread.restype = wt.HANDLE

        h = k32.OpenProcess(0x001F0FFF, False, pid)
        if not h:
            logger.error("OpenProcess failed (run as admin?)")
            return False

        try:
            dll_bytes = dll_path.encode("ascii") + b"\x00"
            mem = k32.VirtualAllocEx(h, None, len(dll_bytes), 0x3000, 0x40)
            if not mem:
                return False

            k32.WriteProcessMemory(h, ctypes.c_void_p(mem), dll_bytes, len(dll_bytes), None)
            load_lib = k32.GetProcAddress(k32.GetModuleHandleA(b"kernel32.dll"), b"LoadLibraryA")
            thread = k32.CreateRemoteThread(
                h, None, 0,
                ctypes.c_void_p(load_lib),
                ctypes.c_void_p(mem), 0, None,
            )
            if not thread:
                return False

            k32.WaitForSingleObject(thread, 10000)
            exit_code = wt.DWORD(0)
            k32.GetExitCodeThread(thread, ctypes.byref(exit_code))
            k32.CloseHandle(thread)
            k32.VirtualFreeEx(h, ctypes.c_void_p(mem), 0, 0x8000)
            return exit_code.value != 0
        finally:
            k32.CloseHandle(h)

    async def inject_job(self, prn_path: str, job_name: str) -> bool:
        """Add PRN file to PrintExp queue with UI refresh."""
        def _do_inject():
            pid = self._ensure_printexp_running()
            if not pid:
                logger.error("PrintExp_X64.exe not running and could not start")
                return False

            if not os.path.exists(self.inject_dll):
                logger.error("DLL not found: %s", self.inject_dll)
                return False

            # Copy DLL to unique temp name (avoid "already loaded" issue)
            import shutil
            temp_dll = os.path.join(self.dll_dir, f"inject_{int(time.time())}.dll")
            shutil.copy2(self.inject_dll, temp_dll)

            # Config and log go next to the temp DLL
            config_path = os.path.join(self.dll_dir, "inject_config.txt")
            log_path = os.path.join(self.dll_dir, "inject_log.txt")

            # Write config
            with open(config_path, "w") as f:
                f.write(prn_path)

            # Clear old log
            if os.path.exists(log_path):
                os.remove(log_path)

            # Inject temp DLL
            if not self._inject_dll(pid, temp_dll):
                logger.error("DLL injection failed (run as admin?)")
                try: os.remove(temp_dll)
                except: pass
                return False

            # Wait for DLL to finish
            success = False
            for _ in range(20):
                time.sleep(0.25)
                if os.path.exists(log_path):
                    with open(log_path) as f:
                        log = f.read()
                    if "done" in log.lower():
                        logger.info("Injection successful: %s", job_name)
                        self._printexp_connected = True
                        success = True
                        break
                    if "err" in log.lower() or "fail" in log.lower():
                        logger.error("Injection failed: %s", log)
                        break

            if not success and not os.path.exists(log_path):
                logger.error("Injection timeout — no log output")

            # Cleanup temp DLL (best effort)
            try: os.remove(temp_dll)
            except: pass

            # Persist job after successful injection
            if success:
                self._persist_job(prn_path)

            return success

        try:
            return await asyncio.to_thread(_do_inject)
        except Exception as e:
            logger.error("inject_job error: %s", e)
            return False

    def _persist_job(self, prn_path: str) -> None:
        """Trigger job persistence after successful injection.

        For DTF v5.8.2: sends SAVE via named pipe (PrintExp writes Unicode TSKF).
        For DTF v5.7.6 / UV: pipe SAVE is a no-op, persistence handled externally.
        """
        try:
            result = self._pipe.save()
            if result and result.get("success"):
                logger.info("Job persisted via pipe SAVE command")
            else:
                logger.debug("Pipe SAVE not available — persistence handled externally")
        except Exception as e:
            logger.debug("Persist attempt: %s", e)

    async def get_status(self) -> PrinterStatus:
        """Check PrintExp status — pipe (vtable) if available, else process check."""
        pid = self._find_pid()
        connected = pid is not None

        printing = False
        # Try named pipe for richer status
        if connected:
            pipe_status = await asyncio.to_thread(self._pipe.status)
            if pipe_status and pipe_status.get("connected"):
                printing = pipe_status.get("printing", False)

        return PrinterStatus(
            type=PrinterType.DTF,
            connected=connected,
            printing=printing,
            current_job=None,
        )

    async def send_command(self, command: str) -> bool:
        """Send command via named pipe (vtable), fallback to WM_COMMAND."""
        # Map dashboard command names to pipe commands
        pipe_map = {
            "pause": "PAUSE",
            "cancel": "CANCEL",
            "check": "CHECK",
            "clean": "CLEAN",
            "home_x": "HOME_X",
            "home_y": "HOME_Y",
            "print": "PRINT",
            "print_start": "PRINT",
        }

        pipe_cmd = pipe_map.get(command)
        if pipe_cmd:
            result = await asyncio.to_thread(self._pipe.send, pipe_cmd)
            if result and result.get("success"):
                logger.info("Pipe command OK: %s", command)
                return True
            if result and "error" not in result:
                # Pipe responded but command failed — don't fallback
                logger.warning("Pipe command failed: %s -> %s", command, result)
                return False
            # Pipe not available — fall through to WM_COMMAND
            logger.debug("Pipe not available for %s, falling back to WM_COMMAND", command)

        # Handle resume specially (not in standard WM_COMMAND maps)
        if command == "resume":
            result = await asyncio.to_thread(self._pipe.send, "RESUME")
            if result and result.get("success"):
                return True
            return False

        # WM_COMMAND fallback
        try:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._wm.send_named, command
            )
        except KeyError:
            logger.warning("Unknown command: %s", command)
            return False
