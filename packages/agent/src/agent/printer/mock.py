"""MockBackend — simulated printer for development and testing.

Simulates realistic timing and configurable failure rates without
needing a physical printer or a running PrintExp process.
"""

from __future__ import annotations

import asyncio
import random
from typing import Optional

from common.models.printer import PrinterStatus, PrinterType


class MockBackend:
    """Fake printer backend that simulates inject/print cycle.

    Useful for:
    - Dashboard development without printer hardware
    - Unit tests that need a backend without ctypes/Win32
    - Running agents with --mock flag
    """

    def __init__(
        self,
        printer_type: PrinterType = PrinterType.DTG,
        inject_delay: float = 2.0,
        failure_rate: float = 0.05,
    ) -> None:
        """
        Args:
            printer_type: Printer type to report in status.
            inject_delay: Simulated inject duration in seconds.
            failure_rate: Probability (0.0–1.0) that inject_job fails.
        """
        self._type = printer_type
        self._inject_delay = inject_delay
        self._failure_rate = failure_rate
        self._printing = False
        self._current_job: Optional[str] = None

        # Fake ink levels (will slowly decrease)
        self._ink_levels: dict[str, float] = {
            "cyan": 85.0,
            "magenta": 72.0,
            "yellow": 91.0,
            "black": 68.0,
            "white": 55.0,
        }

    # ------------------------------------------------------------------
    # PrinterBackend protocol implementation
    # ------------------------------------------------------------------

    async def inject_job(
        self, prn_path: str, job_name: str, workstation: int | None = None
    ) -> bool:
        """Simulate a 2-second injection with configurable failure rate."""
        self._printing = True
        self._current_job = job_name

        await asyncio.sleep(self._inject_delay)

        # Simulate failure
        if random.random() < self._failure_rate:
            self._printing = False
            self._current_job = None
            return False

        # Simulate ink consumption
        for channel in self._ink_levels:
            self._ink_levels[channel] = max(0.0, self._ink_levels[channel] - random.uniform(0.1, 0.5))

        self._printing = False
        self._current_job = None
        return True

    async def get_status(self) -> PrinterStatus:
        """Return a fake but plausible printer status."""
        return PrinterStatus(
            type=self._type,
            connected=True,
            printing=self._printing,
            position_x=random.uniform(0, 50) if self._printing else 0.0,
            position_y=random.uniform(0, 30) if self._printing else 0.0,
            ink_levels=dict(self._ink_levels),
            current_job=self._current_job,
        )

    async def send_command(self, command: str) -> bool:
        """Accept any command instantly — no real effect."""
        # Simulate a tiny network delay
        await asyncio.sleep(0.01)
        return True
