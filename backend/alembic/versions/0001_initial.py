# backend/alembic/versions/0001_initial.py
"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "workers",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("hostname", sa.String(255), nullable=False),
        sa.Column("status", sa.Enum("online", "offline", "draining", name="worker_status"), nullable=False),
        sa.Column("concurrency", sa.Integer, nullable=False, server_default="4"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("admin", "member", name="user_role"), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "projects",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "queues",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", pg.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("max_concurrency", sa.Integer, nullable=False, server_default="5"),
        sa.Column("is_paused", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "name", name="uq_queue_project_name"),
    )

    op.create_table(
        "batches",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", pg.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "jobs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("queue_id", pg.UUID(as_uuid=True), sa.ForeignKey("queues.id"), nullable=False),
        sa.Column("batch_id", pg.UUID(as_uuid=True), sa.ForeignKey("batches.id"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("payload", pg.JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.Enum(
            "pending", "scheduled", "running", "succeeded", "failed",
            "retrying", "dead", "cancelled", name="job_status"), nullable=False, server_default="pending"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, server_default="300"),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default="3"),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("retry_strategy", sa.Enum("fixed", "linear", "exponential", name="retry_strategy"), nullable=False, server_default="exponential"),
        sa.Column("retry_delay_seconds", sa.Integer, nullable=False, server_default="10"),
        sa.Column("cron_expression", sa.String(120), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by", pg.UUID(as_uuid=True), sa.ForeignKey("workers.id"), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_claim", "jobs", ["queue_id", "status", "priority", "run_at"])

    op.create_table(
        "job_executions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", pg.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("worker_id", pg.UUID(as_uuid=True), sa.ForeignKey("workers.id"), nullable=True),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.Enum("running", "succeeded", "failed", "timed_out", name="execution_status"), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("logs", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("job_executions")
    op.drop_table("jobs")
    op.drop_table("batches")
    op.drop_table("queues")
    op.drop_table("projects")
    op.drop_table("users")
    op.drop_table("workers")
    op.drop_table("organizations")
    for enum_name in ("execution_status", "retry_strategy", "job_status", "worker_status", "user_role"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
