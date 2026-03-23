"""HSRP (Hoson Simplified Remote Protocol) client.

Binary protocol used to communicate with the printer mainboard on
192.168.127.10:5001.  Each packet has a 24-byte header followed by
an AES-128-CBC encrypted JSON payload.

Packet layout (24 bytes header):
  Offset  Size  Field
  0       4     Magic: b"HSRP"
  4       4     Command ID (uint32 LE)
  8       4     Sequence number (uint32 LE)
  12      4     Payload length (uint32 LE)
  16      4     CRC32 of plaintext payload (uint32 LE)
  20      4     Reserved / flags (zero)

Crypto delegated to hsrp_crypto.py.
"""

from __future__ import annotations

import json
import socket
import struct
import zlib
from typing import Any

from common.protocols.hsrp_crypto import AES_KEY, AES_IV, encrypt, decrypt

# Re-export for tests / backward compat
_AES_KEY = AES_KEY
_AES_IV = AES_IV
_encrypt = encrypt
_decrypt = decrypt

# --- Constants -----------------------------------------------------------

MAGIC = b"HSRP"
HEADER_FMT = "<4sIIIII"  # magic(4) + cmd(4) + seq(4) + plen(4) + crc(4) + flags(4)
HEADER_SIZE = struct.calcsize(HEADER_FMT)  # == 24


class HSRPCommand:
    """Known HSRP command IDs."""

    GET_PROGRESS = 10
    PRINT_TASK = 11
    CLEAN_HEAD = 14
    RIP_IMPORT = 21


# --- Client ---------------------------------------------------------------

class HSRPClient:
    """Client for the Hoson HSRP mainboard protocol.

    Usage::

        client = HSRPClient()
        client.connect("192.168.127.10", 5001)
        progress = client.get_progress(task_id="job-001")
        client.close()
    """

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._seq: int = 0

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self, host: str = "192.168.127.10", port: int = 5001) -> None:
        """Open TCP connection to the printer mainboard."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect((host, port))
        self._sock = sock

    def close(self) -> None:
        """Close the socket (no-op if already closed)."""
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._sock.close()
            self._sock = None

    def __enter__(self) -> "HSRPClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Low-level packet I/O
    # ------------------------------------------------------------------

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def send_command(self, cmd_id: int, payload_dict: dict[str, Any]) -> dict[str, Any]:
        """Serialize, encrypt, send a command and return the decrypted response."""
        if self._sock is None:
            raise RuntimeError("Not connected — call connect() first")

        plaintext = json.dumps(payload_dict).encode("utf-8")
        ciphertext = encrypt(plaintext)
        crc = zlib.crc32(plaintext) & 0xFFFFFFFF
        seq = self._next_seq()

        header = struct.pack(HEADER_FMT, MAGIC, cmd_id, seq, len(ciphertext), crc, 0)
        self._sock.sendall(header + ciphertext)

        return self._recv_response()

    def _recv_response(self) -> dict[str, Any]:
        """Read one full response packet and return decoded payload."""
        raw_header = self._recvn(HEADER_SIZE)
        magic, cmd_id, seq, plen, crc, flags = struct.unpack(HEADER_FMT, raw_header)

        if magic != MAGIC:
            raise ValueError(f"Bad magic in response: {magic!r}")

        if plen == 0:
            return {}

        raw_payload = self._recvn(plen)
        plaintext = decrypt(raw_payload)

        actual_crc = zlib.crc32(plaintext) & 0xFFFFFFFF
        if actual_crc != crc:
            raise ValueError(f"CRC mismatch: expected {crc:#010x}, got {actual_crc:#010x}")

        return json.loads(plaintext.decode("utf-8"))

    def _recvn(self, n: int) -> bytes:
        """Read exactly n bytes from the socket."""
        buf = bytearray()
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))  # type: ignore[union-attr]
            if not chunk:
                raise ConnectionError("Socket closed while reading")
            buf.extend(chunk)
        return bytes(buf)

    # ------------------------------------------------------------------
    # High-level commands
    # ------------------------------------------------------------------

    def send_import_file(self, prn_path: str) -> dict[str, Any]:
        """Tell the mainboard to import a RIP file."""
        return self.send_command(HSRPCommand.RIP_IMPORT, {"path": prn_path})

    def send_print(self, task_id: str, settings: dict[str, Any] | None = None) -> dict[str, Any]:
        """Dispatch a print task."""
        payload: dict[str, Any] = {"task_id": task_id}
        if settings:
            payload.update(settings)
        return self.send_command(HSRPCommand.PRINT_TASK, payload)

    def get_progress(self, task_id: str) -> dict[str, Any]:
        """Poll print progress for a running task."""
        return self.send_command(HSRPCommand.GET_PROGRESS, {"task_id": task_id})

    def clean_head(self) -> dict[str, Any]:
        """Trigger printhead cleaning cycle."""
        return self.send_command(HSRPCommand.CLEAN_HEAD, {})
