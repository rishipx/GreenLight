"""ORM models. Keep in sync with ``database/schema.sql``."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from greenlight.db.base import Base


def now_utc() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class Operator(Base):
    __tablename__ = "operators"
    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    role: Mapped[str] = mapped_column(String(16), default="APPROVER")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (Index("ix_incidents_status_created", "status", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    service_name: Mapped[str] = mapped_column(String(64))
    host_ip: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(32), default="api")
    severity: Mapped[str] = mapped_column(String(2), default="P1")
    error_trace: Mapped[str] = mapped_column(Text)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    remediation_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    execution_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    approval_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    approval_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    audits = relationship("IncidentAudit", back_populates="incident", cascade="all, delete-orphan")
    job = relationship("RemediationJob", back_populates="incident", uselist=False, cascade="all, delete-orphan")


class RemediationJob(Base):
    __tablename__ = "remediation_jobs"
    __table_args__ = (
        Index("ix_jobs_status_created", "status", "created_at"),
        Index("ix_jobs_status_claimed", "status", "claimed_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), unique=True)
    remediation_key: Mapped[str] = mapped_column(String(64))
    requested_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("operators.telegram_id"))
    status: Mapped[str] = mapped_column(String(16), default="QUEUED")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    incident = relationship("Incident", back_populates="job")


class IncidentAudit(Base):
    __tablename__ = "incident_audits"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"))
    actor_telegram_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(32))
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    incident = relationship("Incident", back_populates="audits")
