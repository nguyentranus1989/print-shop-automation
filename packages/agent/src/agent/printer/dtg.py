"""DTGBackend — real printer integration via TCP 9100 + WriteProcessMemory.

Flow:
  1. Patch filename string in DeviceManager.dll at offset 0x016CDB
     so PrintExp logs the correct job name.
  2. Send .prn file via TCP 9100 to 127.0.0.1:9100.
  3. Poll WM_COMMAND / log to detect print completion.

Win32 helpers delegated to win32_process_helpers.py to stay under 200 lines.
"""

from __future__ import annotations

import asyncio
import sys

from common.config import AgentConfig
from common.models.printer import PrinterStatus, PrinterType
from common.protocols.tcp9100 import TCP9100Client
from common.protocols.wm_command import DTG_BUTTONS, WMCommandController
from agent.printer.win32_process_helpers import (
    find_process_pid,
    get_module_base_address,
    write_process_memory,
)

# DeviceManager.dll memory offset for the rip.prn filename string
_FILENAME_OFFSET = 0x016CDB
# Max bytes to write (null-terminated ASCII, 260 = MAX_PATH)
_FILENAME_MAX_BYTES = 260


class DTGBackend:
    """Production backend for DTG printers running PrintExp.

    Requires Windows + a running PrintExp process.
    On non-Windows the memory patching step is skipped gracefully.
    """

    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._wm = WMCommandController(buttons=DTG_BUTTONS)

    # ------------------------------------------------------------------
    # PrinterBackend protocol implementation
    # ------------------------------------------------------------------

    async def inject_job(self, prn_path: str, job_name: str) -> bool:
        """Patch memory, then stream the PRN file via TCP 9100.

        Returns True on success.
        """
        try:
            # Memory patch runs in executor to avoid blocking event loop
            patched = await asyncio.get_event_loop().run_in_executor(
                None, self._patch_job_name, job_name
            )
            if not patched:
                # Non-fatal: log will show "rip.prn" but job still prints
                pass

            bytes_sent = await asyncio.get_event_loop().run_in_executor(
                None, self._send_prn, prn_path
            )
            return bytes_sent > 0
        except Exception:
            return False

    async def get_status(self) -> PrinterStatus:
        """Return a basic status snapshot (connected = PrintExp window found)."""
        hwnd = await asyncio.get_event_loop().run_in_executor(
            None, self._wm.find_printexp_window
        )
        return PrinterStatus(
            type=PrinterType.DTG,
            connected=hwnd is not None,
            printing=False,  # TODO: parse log for live printing state
        )

    async def send_command(self, command: str) -> bool:
        """Dispatch a named WM_COMMAND to PrintExp."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._wm.send_named, command
        )

    # ------------------------------------------------------------------
    # Internal sync helpers (called via run_in_executor)
    # ------------------------------------------------------------------

    def _patch_job_name(self, job_name: str) -> bool:
        """WriteProcessMemory to set filename in DeviceManager.dll."""
        if sys.platform != "win32":
            return False

        pid = find_process_pid("printexp")
        if pid is None:
            return False

        dll_base = get_module_base_address(pid, "DeviceManager.dll")
        if dll_base is None:
            return False

        target_addr = dll_base + _FILENAME_OFFSET
        encoded = (job_name.encode("ascii", errors="replace") + b"\x00")[:_FILENAME_MAX_BYTES]
        return write_process_memory(pid, target_addr, encoded)

    def _send_prn(self, prn_path: str) -> int:
        """Open TCP 9100 connection, stream file, close.  Returns bytes sent."""
        with TCP9100Client(port=self._config.tcp_port) as client:
            return client.send_file(prn_path)
