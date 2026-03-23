"""JobQueue — create, assign, and update print jobs in SQLite.

All methods are synchronous (sync SQLAlchemy + SQLite).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from common.models.job import JobStatus
from dashboard.db.models import Job


class JobQueue:
    """FIFO queue backed by the SQLite jobs table.

    Usage::

        queue = JobQueue(db_session)
        queue.add_job("ORDER-123", "/nas/job.prn", "dtg")
        job = queue.assign_next("dtg")
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def add_job(
        self,
        order_id: str,
        prn_path: str,
        printer_type: str,
        copies: int = 1,
        notes: str | None = None,
    ) -> Job:
        """Create a new job in PENDING state.

        Args:
            order_id: PodFactory order reference.
            prn_path: Path to the .prn file.
            printer_type: Target printer type ("dtg", "dtf", "uv").
            copies: Number of copies to print.
            notes: Optional free-text notes.

        Returns:
            The created Job ORM instance.
        """
        job = Job(
            id=str(uuid.uuid4()),
            order_id=order_id,
            prn_path=prn_path,
            printer_type=printer_type,
            status=JobStatus.PENDING.value,
            created_at=datetime.utcnow(),
            copies=copies,
            notes=notes,
        )
        self._db.add(job)
        self._db.commit()
        self._db.refresh(job)
        return job

    def assign_next(self, printer_type: str) -> Optional[Job]:
        """Pop the oldest PENDING job for the given printer type.

        Transitions it to QUEUED and assigns it for injection.

        Returns:
            The Job to process, or None if the queue is empty.
        """
        job = (
            self._db.query(Job)
            .filter(
                Job.status == JobStatus.PENDING.value,
                Job.printer_type == printer_type,
            )
            .order_by(Job.created_at.asc())
            .first()
        )
        if job is None:
            return None

        job.status = JobStatus.QUEUED.value
        self._db.commit()
        self._db.refresh(job)
        return job

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        error_message: str | None = None,
    ) -> Optional[Job]:
        """Update job status and set relevant timestamps.

        Args:
            job_id: UUID of the job to update.
            status: New JobStatus value.
            error_message: Error detail if status is FAILED.

        Returns:
            Updated Job, or None if not found.
        """
        job = self._db.query(Job).filter(Job.id == job_id).first()
        if job is None:
            return None

        job.status = status.value

        now = datetime.utcnow()
        if status == JobStatus.PRINTING and job.started_at is None:
            job.started_at = now
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            job.completed_at = now

        if error_message:
            job.error_message = error_message

        self._db.commit()
        self._db.refresh(job)
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Fetch a single job by ID."""
        return self._db.query(Job).filter(Job.id == job_id).first()

    def list_jobs(
        self,
        status: str | None = None,
        printer_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Job]:
        """List jobs with optional filters.

        Args:
            status: Filter by job status string.
            printer_type: Filter by printer type.
            limit: Max records to return.
            offset: Pagination offset.
        """
        query = self._db.query(Job)
        if status:
            query = query.filter(Job.status == status)
        if printer_type:
            query = query.filter(Job.printer_type == printer_type)
        return query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()
