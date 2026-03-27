"""DTGBackend — real printer integration via TCP 9100 + WriteProcessMemory.

Flow:
  1. (Optional) Select target workstation for MULTIWS dual-platen.
  2. Patch filename string in DeviceManager.dll at offset 0x016CDB
     so PrintExp logs the correct job name.
  3. Send .prn file via TCP 9100 to 127.0.0.1:9100.
  4. Poll WM_COMMAND / log to detect print completion.

Win32 helpers delegated to win32_process_helpers.py to stay under 200 lines.
WS log parsing delegated to dtg_ws_log_parser.py.
"""

from __future__ import annotations

import asyncio
import logging
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
from agent.printer.dtg_ws_log_parser import parse_ws_state
from agent.printer.dtg_ws_controller import DTGWorkstationController

logger = logging.getLogger(__name__)

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
        self._ws_ctrl = DTGWorkstationController()

    # ------------------------------------------------------------------
    # PrinterBackend protocol implementation
    # ------------------------------------------------------------------

    async def inject_job(
        self, prn_path: str, job_name: str, workstation: int | None = None
    ) -> bool:
        """Select WS (if specified), patch memory, then stream PRN via TCP 9100.

        Returns True on success.
        """
        try:
            # Select target workstation before sending job
            if workstation is not None:
                ws_ok = await self._select_workstation(workstation)
                if not ws_ok:
                    logger.warning("WS selection failed for WS:%d, proceeding with auto", workstation)

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

            # Restore both WS after job injection to avoid permanent lock
            if workstation is not None:
                await self._restore_both_ws()

            return bytes_sent > 0
        except Exception:
            return False

    async def get_status(self) -> PrinterStatus:
        """Return status snapshot including WS state from PrintExp logs."""
        hwnd = await asyncio.get_event_loop().run_in_executor(
            None, self._wm.find_printexp_window
        )
        ws_state = await asyncio.get_event_loop().run_in_executor(
            None, self._read_ws_state
        )
        return PrinterStatus(
            type=PrinterType.DTG,
            connected=hwnd is not None,
            printing=ws_state.get("printing", False),
            active_ws=ws_state.get("active_ws"),
            ws0_busy=ws_state.get("ws0_busy", False),
            ws1_busy=ws_state.get("ws1_busy", False),
        )

    async def send_command(self, command: str) -> bool:
        """Dispatch a named WM_COMMAND to PrintExp."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._wm.send_named, command
        )

    # ------------------------------------------------------------------
    # Workstation selection — patches CJobProcess+0x90 WS bitmask
    # ------------------------------------------------------------------

    async def _select_workstation(self, ws: int) -> bool:
        """Set target workstation by patching CJobProcess WS bitmask.

        Writes to CJobProcess+0x90 in PrintExp.exe process memory.
        Bitmask: 1=WS:0 only, 2=WS:1 only, 3=both (restore after job).

        Args:
            ws: Workstation index (0 or 1).
        """
        if ws not in (0, 1):
            logger.error("Invalid workstation index: %d (must be 0 or 1)", ws)
            return False

        if sys.platform != "win32":
            logger.info("WS selection skipped (non-Windows)")
            return False

        pid = find_process_pid("printexp")
        if pid is None:
            logger.warning("PrintExp not running — cannot select WS")
            return False

        return await asyncio.get_event_loop().run_in_executor(
            None, self._ws_ctrl.select_workstation, pid, ws
        )

    async def _restore_both_ws(self) -> None:
        """Restore normal dual-WS operation after a targeted job injection."""
        if sys.platform != "win32":
            return
        pid = find_process_pid("printexp")
        if pid is None:
            return
        await asyncio.get_event_loop().run_in_executor(
            None, self._ws_ctrl.restore_both, pid
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

    def _read_ws_state(self) -> dict:
        """Parse PrintExp log for workstation state (sync, called in executor)."""
        printexp_path = self._config.printexp_path
        if not printexp_path:
            return {}
        return parse_ws_state(printexp_path)
