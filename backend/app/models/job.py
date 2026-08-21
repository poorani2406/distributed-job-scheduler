# backend/app/models/job.py
import uuid
import enum
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Integer, func, Enum, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD = "dead"
    CANCELLED = "cancelled"


class RetryStrategy(str, enum.Enum):
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_claim", "queue_id", "status", "priority", "run_at"),
        Index("ix_jobs_queue_id_status", "queue_id", "status"),
        Index("ix_jobs_queue_id_run_at", "queue_id", "run_at"),
        Index("ix_jobs_claimed_by", "claimed_by"),
        Index("ix_jobs_idempotency_key", "idempotency_key"),
        UniqueConstraint("queue_id", "idempotency_key", name="uq_jobs_queue_idempotency_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    queue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("queues.id"), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("batches.id"), nullable=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)

    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", values_callable=lambda x: [e.value for e in x]),
        default=JobStatus.PENDING,
        index=True
    )
    priority: Mapped[int] = mapped_column(Integer, default=0)  # higher = more urgent

    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300)

    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    retry_strategy: Mapped[RetryStrategy] = mapped_column(
        Enum(RetryStrategy, name="retry_strategy", values_callable=lambda x: [e.value for e in x]),
        default=RetryStrategy.EXPONENTIAL
    )
    retry_delay_seconds: Mapped[int] = mapped_column(Integer, default=10)

    cron_expression: Mapped[str | None] = mapped_column(String(120), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    claimed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workers.id"), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    queue: Mapped["Queue"] = relationship(back_populates="jobs")
    batch: Mapped["Batch"] = relationship(back_populates="jobs")
    executions: Mapped[list["JobExecution"]] = relationship(back_populates="job", order_by="JobExecution.started_at")