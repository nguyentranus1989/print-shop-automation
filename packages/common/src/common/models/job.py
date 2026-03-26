"""Job domain model — lifecycle states and job data."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """All possible states a print job can be in."""

    PENDING = "pending"      # created, waiting to be picked up
    QUEUED = "queued"        # assigned to a printer, waiting for inject
    INJECTING = "injecting"  # DLL injection in progress
    SENT = "sent"            # file injected into PrintExp queue
    PRINTING = "printing"    # PrintExp is actively printing (needs hardware monitoring)
    COMPLETED = "completed"  # print finished (needs hardware monitoring)
    FAILED = "failed"        # error during inject or print
    CANCELLED = "cancelled"  # manually cancelled


class Job(BaseModel):
    """A single print job request.

    Pydantic v2 model — use model_validate() and model_dump().
    """

    id: str = Field(..., description="UUID for this job")
    order_id: str = Field(..., description="PodFactory order reference")
    prn_path: str = Field(..., description="Absolute path to .prn file on NAS or local disk")
    printer_type: str = Field(..., description="Target printer type: dtg, dtf, uv")
    status: JobStatus = Field(default=JobStatus.PENDING)

    # timestamps — all UTC
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # optional metadata
    copies: int = Field(default=1, ge=1)
    notes: Optional[str] = None
    error_message: Optional[str] = None

    # agent that owns this job (agent URL or name)
    assigned_agent: Optional[str] = None

    model_config = {"use_enum_values": True}

    def is_terminal(self) -> bool:
        """True if the job has reached a final state (no further transitions)."""
        return self.status in (
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.SENT,
        )

    def duration_seconds(self) -> Optional[float]:
        """Elapsed seconds from start to completion, or None if not complete."""
        if self.started_at is None or self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()
