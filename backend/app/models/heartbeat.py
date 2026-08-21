# backend/app/models/heartbeat.py
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, func, String, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    __table_args__ = (
        Index("ix_worker_heartbeats_worker_id_timestamp", "worker_id", "timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workers.id", ondelete="CASCADE"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    active_jobs: Mapped[list] = mapped_column(JSONB, default=list)
    metadata_info: Mapped[dict] = mapped_column(JSONB, default=dict, name="metadata")  # mapping metadata to name 'metadata' to avoid reserved keyword collision if any

    worker = relationship("Worker", backref="heartbeats")
