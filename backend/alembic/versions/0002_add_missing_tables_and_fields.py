"""add missing tables and fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create retry_policies table first (so queues can reference it)
    op.create_table(
        "retry_policies",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", pg.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("strategy", sa.String(50), nullable=False, server_default="exponential"),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default="3"),
        sa.Column("delay_seconds", sa.Integer, nullable=False, server_default="10"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 2. Add columns to queues
    op.add_column("queues", sa.Column("description", sa.String(500), nullable=True))
    op.add_column("queues", sa.Column("priority", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("queues", sa.Column("retry_policy_id", pg.UUID(as_uuid=True), sa.ForeignKey("retry_policies.id", ondelete="SET NULL"), nullable=True))

    # 3. Create worker_heartbeats
    op.create_table(
        "worker_heartbeats",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("worker_id", pg.UUID(as_uuid=True), sa.ForeignKey("workers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("active_jobs", pg.JSONB, nullable=False, server_default="[]"),
        sa.Column("metadata", pg.JSONB, nullable=False, server_default="{}"),
    )

    # 4. Create job_logs
    op.create_table(
        "job_logs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", pg.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("worker_id", pg.UUID(as_uuid=True), sa.ForeignKey("workers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_job_logs_job_id", "job_logs", ["job_id"])

    # 5. Create scheduled_jobs
    op.create_table(
        "scheduled_jobs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", pg.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cron_expression", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 6. Create dead_letter_queue_entries
    op.create_table(
        "dead_letter_queue_entries",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", pg.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("queue_id", pg.UUID(as_uuid=True), sa.ForeignKey("queues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("worker_id", pg.UUID(as_uuid=True), sa.ForeignKey("workers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 7. Add idempotency_key to jobs
    op.add_column("jobs", sa.Column("idempotency_key", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_jobs_queue_idempotency_key", "jobs", ["queue_id", "idempotency_key"])



def downgrade() -> None:
    op.drop_constraint("uq_jobs_queue_idempotency_key", "jobs", type_="unique")
    op.drop_column("jobs", "idempotency_key")
    op.drop_table("dead_letter_queue_entries")
    op.drop_table("scheduled_jobs")
    op.drop_index("ix_job_logs_job_id", "job_logs")
    op.drop_table("job_logs")
    op.drop_table("worker_heartbeats")
    op.drop_column("queues", "retry_policy_id")
    op.drop_column("queues", "priority")
    op.drop_column("queues", "description")
    op.drop_table("retry_policies")
