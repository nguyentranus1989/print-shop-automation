"""TCP 9100 raw print protocol client.

Sends a .prn file to PrintExp via raw TCP socket on 127.0.0.1:9100.
PrintExp listens on this port and accepts raw printer data (PRN format).
"""

from __future__ import annotations

import socket
from pathlib import Path

# 64 KB chunks — large enough to saturate loopback without excessive syscalls
_CHUNK_SIZE = 65536


class TCP9100Client:
    """Minimal raw TCP client for the JetDirect / port-9100 print protocol.

    Usage::

        client = TCP9100Client()
        client.connect()
        client.send_file("/path/to/job.prn")
        client.close()
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9100, timeout: float = 30.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Open TCP connection to PrintExp.  Raises OSError on failure."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect((self.host, self.port))
        self._sock = sock

    def close(self) -> None:
        """Gracefully close the socket (no-op if already closed)."""
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._sock.close()
            self._sock = None

    def __enter__(self) -> "TCP9100Client":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # File transmission
    # ------------------------------------------------------------------

    def send_file(self, path: str | Path) -> int:
        """Stream file contents to the printer socket.

        Args:
            path: Absolute path to the .prn file.

        Returns:
            Total bytes sent.

        Raises:
            RuntimeError: If not connected.
            OSError: On socket or file I/O error.
        """
        if self._sock is None:
            raise RuntimeError("Not connected — call connect() first")

        prn_path = Path(path)
        if not prn_path.exists():
            raise FileNotFoundError(f"PRN file not found: {prn_path}")

        total_sent = 0
        with prn_path.open("rb") as fh:
            while chunk := fh.read(_CHUNK_SIZE):
                self._sock.sendall(chunk)
                total_sent += len(chunk)

        return total_sent
