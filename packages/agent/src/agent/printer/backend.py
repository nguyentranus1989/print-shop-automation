"""PrinterBackend protocol — structural subtyping interface for all printer implementations.

Any class that implements these three async methods is a valid backend,
no explicit inheritance required (duck typing via Protocol).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from common.models.printer import PrinterStatus


@runtime_checkable
class PrinterBackend(Protocol):
    """Interface every concrete printer backend must satisfy."""

    async def inject_job(
        self, prn_path: str, job_name: str, workstation: int | None = None
    ) -> bool:
        """Send a .prn file to the printer and trigger print.

        Args:
            prn_path: Absolute path to the .prn file.
            job_name: Human-readable job identifier (patched into memory).
            workstation: Target WS index (0 or 1) for MULTIWS DTG printers.
                         None = let PrintExp auto-allocate.

        Returns:
            True if injection succeeded, False on error.
        """
        ...

    async def get_status(self) -> PrinterStatus:
        """Query the printer's current live status.

        Returns:
            A populated PrinterStatus snapshot.
        """
        ...

    async def send_command(self, command: str) -> bool:
        """Send a named control command (move_left, print_start, etc.).

        Args:
            command: Action name from the printer's button map.

        Returns:
            True if the command was dispatched, False on error.
        """
        ...
