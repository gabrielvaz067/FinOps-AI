from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    seed: Mapped[int] = mapped_column(Integer)
    row_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    segment: Mapped[str] = mapped_column(String(40))


class Channel(Base):
    __tablename__ = "channels"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_transaction_amount"),
        CheckConstraint("status IN ('approved', 'declined')", name="ck_transaction_status"),
        CheckConstraint("direction IN ('inflow', 'outflow')", name="ck_transaction_direction"),
        Index("ix_transaction_bucket", "account_id", "channel_id", "occurred_at"),
        Index("ix_transaction_time_status", "occurred_at", "status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    amount_cents: Mapped[int] = mapped_column(Integer)
    direction: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(10))
    payment_ref: Mapped[str] = mapped_column(String(60), index=True)


class SyntheticLabel(Base):
    """Ground truth is deliberately separated from the feature source table."""

    __tablename__ = "synthetic_labels"
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(30), index=True)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(100), unique=True)
    model_version: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    train_end: Mapped[date] = mapped_column(Date)
    metrics: Mapped[dict] = mapped_column(JSON)
    metadata_json: Mapped[dict] = mapped_column(JSON)


class Anomaly(Base):
    __tablename__ = "anomalies"
    __table_args__ = (
        UniqueConstraint("run_id", "account_id", "channel_id", "day", name="uq_anomaly_bucket"),
        Index("ix_anomaly_severity_day", "severity", "day"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("pipeline_runs.id"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"))
    day: Mapped[date] = mapped_column(Date)
    severity: Mapped[str] = mapped_column(String(10))
    score: Mapped[float] = mapped_column(Float)
    ml_detected: Mapped[bool]
    rule_detected: Mapped[bool]
    reasons: Mapped[list] = mapped_column(JSON)
    evidence: Mapped[dict] = mapped_column(JSON)
    model_version: Mapped[str] = mapped_column(String(60))


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[int] = mapped_column(primary_key=True)
    anomaly_id: Mapped[int] = mapped_column(ForeignKey("anomalies.id"), index=True)
    source: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(80))
    content: Mapped[dict] = mapped_column(JSON)
    fallback_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class GeminiAttempt(Base):
    __tablename__ = "gemini_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), unique=True)
    provider: Mapped[str] = mapped_column(String(20))
    requested_model: Mapped[str] = mapped_column(String(80))
    attempted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str] = mapped_column(String(40))


class AutomationRun(Base):
    __tablename__ = "automation_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="running")
    processed: Mapped[int] = mapped_column(default=0)
    skipped: Mapped[int] = mapped_column(default=0)
    failed: Mapped[int] = mapped_column(default=0)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("anomaly_id", "mode", name="uq_notification_delivery"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    anomaly_id: Mapped[int] = mapped_column(ForeignKey("anomalies.id"))
    mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(default=0)


class NotificationAttempt(Base):
    __tablename__ = "notification_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    notification_id: Mapped[int] = mapped_column(ForeignKey("notifications.id"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("automation_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    status: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(String(250))
