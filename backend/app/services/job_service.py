# backend/app/services/job_service.py
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.job import Job, JobStatus
from app.models.batch import Batch
from app.models.queue import Queue
from app.models.log import JobLog
from app.models.scheduled_job import ScheduledJob
from app.models.dlq import DeadLetterQueueEntry
from app.schemas import JobCreate, BatchJobCreate

VALID_TRANSITIONS = {
    JobStatus.PENDING: {JobStatus.RUNNING, JobStatus.CANCELLED},
    JobStatus.SCHEDULED: {JobStatus.RUNNING, JobStatus.CANCELLED},
    JobStatus.RETRYING: {JobStatus.RUNNING, JobStatus.CANCELLED},
    JobStatus.RUNNING: {JobStatus.SUCCEEDED, JobStatus.RETRYING, JobStatus.DEAD, JobStatus.CANCELLED, JobStatus.PENDING},
    JobStatus.DEAD: {JobStatus.PENDING},
    JobStatus.SUCCEEDED: set(),
    JobStatus.CANCELLED: set(),
}


async def transition_job_status(
    db: AsyncSession,
    job: Job,
    target_status: JobStatus,
    worker_id: uuid.UUID | None = None,
    error: str | None = None,
    message: str | None = None
) -> Job:
    current_status = job.status
    if current_status == target_status:
        return job

    allowed = VALID_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state transition from {current_status} to {target_status}"
        )

    job.status = target_status
    now = datetime.now(timezone.utc)
    job.updated_at = now

    # Leaving scheduled status -> clean up scheduled_jobs entry
    if current_status == JobStatus.SCHEDULED:
        await db.execute(delete(ScheduledJob).where(ScheduledJob.job_id == job.id))

    # Entering scheduled or retrying -> track in scheduled_jobs table
    if target_status in (JobStatus.SCHEDULED, JobStatus.RETRYING):
        await db.execute(delete(ScheduledJob).where(ScheduledJob.job_id == job.id))
        db.add(ScheduledJob(
            job_id=job.id,
            run_at=job.run_at,
            cron_expression=job.cron_expression
        ))

    # Transitioning to DEAD -> move to dead_letter_queue_entries
    if target_status == JobStatus.DEAD:
        await db.execute(delete(DeadLetterQueueEntry).where(DeadLetterQueueEntry.job_id == job.id))
        db.add(DeadLetterQueueEntry(
            job_id=job.id,
            queue_id=job.queue_id,
            worker_id=worker_id or job.claimed_by,
            failure_reason=message or error or "Max retries exceeded",
            last_error=error,
            retry_count=job.retry_count,
            created_at=now
        ))

    # Resetting from DEAD to PENDING -> clean up DLQ entry
    if current_status == JobStatus.DEAD and target_status == JobStatus.PENDING:
        await db.execute(delete(DeadLetterQueueEntry).where(DeadLetterQueueEntry.job_id == job.id))

    # Log transition event in JobLog
    event_name = f"JOB_{target_status.value.upper()}"
    if target_status == JobStatus.RETRYING:
        event_name = "RETRY_SCHEDULED"
    elif target_status == JobStatus.DEAD:
        event_name = "MOVED_TO_DLQ"

    db.add(JobLog(
        job_id=job.id,
        worker_id=worker_id or job.claimed_by,
        event=event_name,
        message=message or f"Transitioned from {current_status} to {target_status}",
        created_at=now
    ))

    return job


async def get_owned_queue(db: AsyncSession, queue_id: uuid.UUID, org_id: uuid.UUID) -> Queue:
    result = await db.execute(
        select(Queue).join(Queue.project).where(
            Queue.id == queue_id, Queue.project.has(org_id=org_id)
        )
    )
    queue = result.scalar_one_or_none()
    if not queue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue not found")
    return queue


def _build_job(queue_id: uuid.UUID, data: JobCreate, batch_id: uuid.UUID | None = None) -> Job:
    run_at = data.run_at or datetime.now(timezone.utc)
    if data.job_type == "delayed" and data.delay_seconds is not None:
        run_at = datetime.now(timezone.utc) + timedelta(seconds=data.delay_seconds)

    status_ = JobStatus.SCHEDULED if (data.run_at or data.job_type == "delayed" or data.job_type == "scheduled") else JobStatus.PENDING

    if data.cron_expression:
        from croniter import croniter
        cron = croniter(data.cron_expression, datetime.now(timezone.utc))
        run_at = cron.get_next(datetime)
        status_ = JobStatus.SCHEDULED

    return Job(
        queue_id=queue_id,
        batch_id=batch_id,
        name=data.name,
        payload=data.payload,
        priority=data.priority,
        run_at=run_at,
        status=status_,
        timeout_seconds=data.timeout_seconds,
        max_retries=data.max_retries,
        retry_strategy=data.retry_strategy,
        retry_delay_seconds=data.retry_delay_seconds,
        cron_expression=data.cron_expression,
        next_run_at=run_at if data.cron_expression else None,
        idempotency_key=data.idempotency_key if hasattr(data, "idempotency_key") else None,
    )


async def create_job(db: AsyncSession, queue_id: uuid.UUID, data: JobCreate) -> Job:
    if hasattr(data, "idempotency_key") and data.idempotency_key:
        existing = await db.execute(
            select(Job).where(Job.queue_id == queue_id, Job.idempotency_key == data.idempotency_key)
        )
        existing_job = existing.scalar_one_or_none()
        if existing_job:
            return existing_job

    job = _build_job(queue_id, data)
    db.add(job)
    await db.flush()

    db.add(JobLog(
        job_id=job.id,
        event="JOB_CREATED",
        message=f"Job created with status {job.status}",
        created_at=datetime.now(timezone.utc)
    ))

    if job.status == JobStatus.SCHEDULED:
        db.add(ScheduledJob(
            job_id=job.id,
            run_at=job.run_at,
            cron_expression=job.cron_expression
        ))

    await db.commit()
    await db.refresh(job)
    return job


async def create_batch_jobs(db: AsyncSession, project_id: uuid.UUID, queue_id: uuid.UUID, data: BatchJobCreate) -> Batch:
    batch = Batch(project_id=project_id, name=data.batch_name)
    db.add(batch)
    await db.flush()

    now = datetime.now(timezone.utc)
    for job_data in data.jobs:
        if hasattr(job_data, "idempotency_key") and job_data.idempotency_key:
            existing = await db.execute(
                select(Job).where(Job.queue_id == queue_id, Job.idempotency_key == job_data.idempotency_key)
            )
            existing_job = existing.scalar_one_or_none()
            if existing_job:
                existing_job.batch_id = batch.id
                continue

        job = _build_job(queue_id, job_data, batch_id=batch.id)
        db.add(job)
        await db.flush()

        db.add(JobLog(
            job_id=job.id,
            event="JOB_CREATED",
            message=f"Batch job created with status {job.status}",
            created_at=now
        ))

        if job.status == JobStatus.SCHEDULED:
            db.add(ScheduledJob(
                job_id=job.id,
                run_at=job.run_at,
                cron_expression=job.cron_expression
            ))

    await db.commit()
    result = await db.execute(
        select(Batch).options(selectinload(Batch.jobs)).where(Batch.id == batch.id)
    )
    return result.scalar_one()


async def cancel_job(db: AsyncSession, job: Job) -> Job:
    if job.status in (JobStatus.SUCCEEDED, JobStatus.DEAD, JobStatus.CANCELLED):
        raise HTTPException(status_code=400, detail=f"Cannot cancel job in status {job.status}")
    await transition_job_status(db, job, JobStatus.CANCELLED, message="Job cancelled by user")
    await db.commit()
    await db.refresh(job)
    return job


async def retry_dead_job(db: AsyncSession, job: Job) -> Job:
    job.retry_count = 0
    job.run_at = datetime.now(timezone.utc)
    job.claimed_by = None
    job.claimed_at = None

    await transition_job_status(db, job, JobStatus.PENDING, message="Job retried by user")
    await db.commit()
    await db.refresh(job)
    return job