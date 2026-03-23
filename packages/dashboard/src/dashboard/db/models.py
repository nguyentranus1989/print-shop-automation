"""SQLAlchemy ORM models for the dashboard database.

Tables:
  - printers    — registered agent endpoints and their last-known status
  - jobs        — all print jobs (queue + history)
  - ink_usage   — periodic ink level snapshots per printer
  - print_events — log of significant print lifecycle events
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dashboard.db.database import Base


class Printer(Base):
    """A registered printer agent."""

    __tablename__ = "printers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_url: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    printer_type: Mapped[str] = mapped_column(String(20), nullable=False, default="dtg")

    # Human-readable status string: online/offline/printing/error
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="offline")

    # Last-known status (updated by polling loop)
    connected: Mapped[bool] = mapped_column(Integer, default=0)  # SQLite has no BOOL
    printing: Mapped[bool] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Registration timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="printer")
    ink_usage_records: Mapped[list["InkUsage"]] = relationship("InkUsage", back_populates="printer")
    events: Mapped[list["PrintEvent"]] = relationship("PrintEvent", back_populates="printer")

    def __repr__(self) -> str:
        return f"<Printer id={self.id} name={self.name!r} type={self.printer_type}>"


class Job(Base):
    """A single print job — queue entry and history record."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    order_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    prn_path: Mapped[str] = mapped_column(String(500), nullable=False)
    printer_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)

    # Timestamps (UTC)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    copies: Mapped[int] = mapped_column(Integer, default=1)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # FK to printer that owns this job
    printer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("printers.id"), nullable=True)
    printer: Mapped["Printer | None"] = relationship("Printer", back_populates="jobs")

    def __repr__(self) -> str:
        return f"<Job id={self.id!r} order={self.order_id!r} status={self.status}>"


class InkUsage(Base):
    """Periodic ink level snapshot for a printer."""

    __tablename__ = "ink_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    printer_id: Mapped[int] = mapped_column(Integer, ForeignKey("printers.id"), nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # Channel levels as percentage (0–100)
    cyan: Mapped[float | None] = mapped_column(Float, nullable=True)
    magenta: Mapped[float | None] = mapped_column(Float, nullable=True)
    yellow: Mapped[float | None] = mapped_column(Float, nullable=True)
    black: Mapped[float | None] = mapped_column(Float, nullable=True)
    white: Mapped[float | None] = mapped_column(Float, nullable=True)

    printer: Mapped["Printer"] = relationship("Printer", back_populates="ink_usage_records")

    def __repr__(self) -> str:
        return f"<InkUsage printer_id={self.printer_id} at={self.recorded_at}>"


class PrintEvent(Base):
    """Significant lifecycle event for a printer or job."""

    __tablename__ = "print_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    printer_id: Mapped[int] = mapped_column(Integer, ForeignKey("printers.id"), nullable=False, index=True)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # started, completed, error, etc.
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    printer: Mapped["Printer"] = relationship("Printer", back_populates="events")

    def __repr__(self) -> str:
        return f"<PrintEvent printer_id={self.printer_id} type={self.event_type!r}>"
