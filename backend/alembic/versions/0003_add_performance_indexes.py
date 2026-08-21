"""add performance indexes

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add indexes to jobs table
    op.create_index("ix_jobs_queue_id_status", "jobs", ["queue_id", "status"])
    op.create_index("ix_jobs_queue_id_run_at", "jobs", ["queue_id", "run_at"])
    op.create_index("ix_jobs_claimed_by", "jobs", ["claimed_by"])
    op.create_index("ix_jobs_idempotency_key", "jobs", ["idempotency_key"])

    # 2. Add indexes to job_executions
    op.create_index("ix_job_executions_job_id", "job_executions", ["job_id"])
    op.create_index("ix_job_executions_worker_id", "job_executions", ["worker_id"])

    # 3. Add index to scheduled_jobs
    op.create_index("ix_scheduled_jobs_run_at", "scheduled_jobs", ["run_at"])

    # 4. Add index to worker_heartbeats
    op.create_index("ix_worker_heartbeats_worker_id_timestamp", "worker_heartbeats", ["worker_id", "timestamp"])

    # 5. Add index to retry_policies
    op.create_index("ix_retry_policies_project_id", "retry_policies", ["project_id"])

    # 6. Add index to dead_letter_queue_entries
    op.create_index("ix_dlq_queue_id", "dead_letter_queue_entries", ["queue_id"])


def downgrade() -> None:
    op.drop_index("ix_dlq_queue_id", "dead_letter_queue_entries")
    op.drop_index("ix_retry_policies_project_id", "retry_policies")
    op.drop_index("ix_worker_heartbeats_worker_id_timestamp", "worker_heartbeats")
    op.drop_index("ix_scheduled_jobs_run_at", "scheduled_jobs")
    op.drop_index("ix_job_executions_worker_id", "job_executions")
    op.drop_index("ix_job_executions_job_id", "job_executions")
    op.drop_index("ix_jobs_idempotency_key", "jobs")
    op.drop_index("ix_jobs_claimed_by", "jobs")
    op.drop_index("ix_jobs_queue_id_run_at", "jobs")
    op.drop_index("ix_jobs_queue_id_status", "jobs")
