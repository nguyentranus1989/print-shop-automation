"""Named pipe client for PrintFlow Bridge DLL.

Sends JSON commands to the bridge DLL running inside PrintExp
and returns parsed responses.
"""

import json
import struct
import time

PIPE_NAME = r"\\.\pipe\PrintFlowBridge"
PIPE_TIMEOUT_MS = 5000


class BridgeError(Exception):
    """Bridge communication error."""


class BridgeClient:
    """Client for the PrintFlow bridge DLL named pipe."""

    def __init__(self, pipe_name: str = PIPE_NAME, timeout_ms: int = PIPE_TIMEOUT_MS):
        self.pipe_name = pipe_name
        self.timeout_ms = timeout_ms

    def _send(self, request: dict) -> dict:
        """Send JSON request via named pipe, return parsed response."""
        import ctypes
        import ctypes.wintypes as wt

        k32 = ctypes.windll.kernel32

        # Open pipe
        GENERIC_READ = 0x80000000
        GENERIC_WRITE = 0x40000000
        OPEN_EXISTING = 3

        handle = k32.CreateFileA(
            self.pipe_name.encode("ascii"),
            GENERIC_READ | GENERIC_WRITE,
            0, None, OPEN_EXISTING, 0, None,
        )
        if handle == -1 or handle == 0xFFFFFFFF:
            # Try waiting for pipe to become available
            k32.WaitNamedPipeA(self.pipe_name.encode("ascii"), self.timeout_ms)
            handle = k32.CreateFileA(
                self.pipe_name.encode("ascii"),
                GENERIC_READ | GENERIC_WRITE,
                0, None, OPEN_EXISTING, 0, None,
            )
            if handle == -1 or handle == 0xFFFFFFFF:
                raise BridgeError("Cannot connect to bridge pipe (is DLL injected?)")

        try:
            # Set pipe to message mode
            mode = ctypes.c_ulong(0x02)  # PIPE_READMODE_MESSAGE
            k32.SetNamedPipeHandleState(handle, ctypes.byref(mode), None, None)

            # Write request
            data = json.dumps(request).encode("utf-8")
            written = ctypes.c_ulong(0)
            if not k32.WriteFile(handle, data, len(data), ctypes.byref(written), None):
                raise BridgeError(f"WriteFile failed (error {k32.GetLastError()})")

            # Read response
            buf = ctypes.create_string_buffer(4096)
            read_bytes = ctypes.c_ulong(0)
            if not k32.ReadFile(handle, buf, 4096, ctypes.byref(read_bytes), None):
                raise BridgeError(f"ReadFile failed (error {k32.GetLastError()})")

            response_str = buf.value[:read_bytes.value].decode("utf-8", errors="replace")
            return json.loads(response_str)

        finally:
            k32.CloseHandle(handle)

    def ping(self) -> bool:
        """Check if bridge is alive."""
        try:
            result = self._send({"cmd": "ping"})
            return result.get("ok", False)
        except (BridgeError, json.JSONDecodeError):
            return False

    def add_file(self, prn_path: str) -> bool:
        """Add PRN file to PrintExp queue with UI refresh."""
        result = self._send({"cmd": "add_file", "path": prn_path})
        if not result.get("ok"):
            raise BridgeError(result.get("error", "unknown error"))
        return True

    def get_status(self) -> dict:
        """Get PrintExp status (print state, ready, queue counts)."""
        result = self._send({"cmd": "get_status"})
        if not result.get("ok"):
            raise BridgeError(result.get("error", "unknown error"))
        return result

    def control(self, action: str) -> bool:
        """Send control command (pause, resume, etc.)."""
        result = self._send({"cmd": "control", "action": action})
        if not result.get("ok"):
            raise BridgeError(result.get("error", "unknown error"))
        return True

    def is_connected(self) -> bool:
        """Check if bridge pipe exists (DLL is loaded in PrintExp)."""
        try:
            return self.ping()
        except Exception:
            return False
