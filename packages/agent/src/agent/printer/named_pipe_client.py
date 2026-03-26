"""Named pipe client for communicating with the PrintFlow Control DLL.

Sends text commands to \\.\pipe\PrintFlowControl and reads JSON responses.
Falls back gracefully if pipe is not available (DLL not loaded).
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

PIPE_NAME = r"\\.\pipe\PrintFlowControl"


class NamedPipeClient:
    """Send commands to the PrintFlow Control DLL via named pipe."""

    def __init__(self, pipe_name: str = PIPE_NAME) -> None:
        self._pipe_name = pipe_name

    def is_available(self) -> bool:
        """Check if the named pipe exists (DLL is loaded and listening)."""
        try:
            import ctypes
            import ctypes.wintypes as wt
            k32 = ctypes.windll.kernel32
            k32.CreateFileA.restype = wt.HANDLE
            INVALID_HANDLE = wt.HANDLE(-1).value
            handle = k32.CreateFileA(
                self._pipe_name.encode("ascii"),
                0x80000000 | 0x40000000,  # GENERIC_READ | GENERIC_WRITE
                0, None,
                3,  # OPEN_EXISTING
                0, None,
            )
            if handle == INVALID_HANDLE:
                return False
            k32.CloseHandle(handle)
            return True
        except Exception:
            return False

    def send(self, command: str) -> dict[str, Any] | None:
        """Send a command string and return parsed JSON response.

        Returns None if pipe is not available or communication fails.
        """
        try:
            import ctypes
            import ctypes.wintypes as wt

            k32 = ctypes.windll.kernel32
            k32.CreateFileA.restype = wt.HANDLE
            INVALID_HANDLE = wt.HANDLE(-1).value

            # Open pipe
            handle = k32.CreateFileA(
                self._pipe_name.encode("ascii"),
                0x80000000 | 0x40000000,  # GENERIC_READ | GENERIC_WRITE
                0, None,
                3,  # OPEN_EXISTING
                0, None,
            )
            if handle == INVALID_HANDLE:
                return None

            try:
                # Set pipe mode to message read
                mode = wt.DWORD(0x00000002)  # PIPE_READMODE_MESSAGE
                k32.SetNamedPipeHandleState(handle, ctypes.byref(mode), None, None)

                # Write command
                cmd_bytes = (command.strip() + "\n").encode("ascii")
                written = wt.DWORD(0)
                ok = k32.WriteFile(
                    handle, cmd_bytes, len(cmd_bytes),
                    ctypes.byref(written), None,
                )
                if not ok:
                    return None

                # Read response
                buf = ctypes.create_string_buffer(4096)
                read_bytes = wt.DWORD(0)
                ok = k32.ReadFile(
                    handle, buf, 4095,
                    ctypes.byref(read_bytes), None,
                )
                if not ok or read_bytes.value == 0:
                    return None

                response = buf.raw[:read_bytes.value].decode("ascii", errors="replace").strip()
                return json.loads(response)

            finally:
                k32.CloseHandle(handle)

        except json.JSONDecodeError as e:
            logger.warning("Pipe response not valid JSON: %s", e)
            return None
        except Exception as e:
            logger.debug("Pipe communication failed: %s", e)
            return None

    def status(self) -> dict[str, Any] | None:
        """Query printer status via pipe."""
        return self.send("STATUS")

    def pause(self) -> dict[str, Any] | None:
        return self.send("PAUSE")

    def resume(self) -> dict[str, Any] | None:
        return self.send("RESUME")

    def cancel(self) -> dict[str, Any] | None:
        return self.send("CANCEL")

    def save(self) -> dict[str, Any] | None:
        """Trigger job list save (for v5.8.2 Unicode TSKF persistence)."""
        return self.send("SAVE")

    def task_count(self) -> int:
        """Get number of tasks loaded in PrintExp."""
        result = self.send("TASK_COUNT")
        return result.get("task_count", 0) if result else 0

    def ping(self) -> bool:
        """Check if DLL is responsive."""
        result = self.send("PING")
        return result is not None and result.get("pong") is True
