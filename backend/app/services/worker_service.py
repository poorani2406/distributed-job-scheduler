# backend/app/services/worker_service.py
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import text, select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models.worker import Worker, WorkerStatus
from app.models.job import Job, JobStatus, RetryStrategy
from app.models.execution import JobExecution, ExecutionStatus
from app.models.heartbeat import WorkerHeartbeat
from app.models.log import JobLog
from app.models.queue import Queue
from app.config import settings
from app.services.job_service import transition_job_status
CLAIMABLE_STATUSES = ("pending", "scheduled", "retrying")


async def register_worker(db: AsyncSession, hostname: str, concurrency: int) -> Worker:
    worker = Worker(hostname=hostname, concurrency=concurrency, status=WorkerStatus.ONLINE)
    db.add(worker)
    await db.commit()
    await db.refresh(worker)
    return worker


async def deregister_worker(db: AsyncSession, worker_id: uuid.UUID) -> None:
    result = await db.execute(select(Worker).where(Worker.id == worker_id))
    worker = result.scalar_one_or_none()
    if worker:
        worker.status = WorkerStatus.OFFLINE
        worker.last_heartbeat = datetime.now(timezone.utc)

    # Requeue running jobs claimed by this worker
    running_jobs_res = await db.execute(
        select(Job).where(Job.claimed_by == worker_id, Job.status == JobStatus.RUNNING)
    )
    running_jobs = running_jobs_res.scalars().all()
    now = datetime.now(timezone.utc)
    for job in running_jobs:
        job.claimed_by = None
        job.claimed_at = None
        job.heartbeat_at = None

        await transition_job_status(
            db, job, JobStatus.PENDING,
            worker_id=worker_id,
            message="Worker deregistered/shutdown, job returned to PENDING"
        )

        exec_res = await db.execute(
            select(JobExecution)
            .where(JobExecution.job_id == job.id, JobExecution.status == ExecutionStatus.RUNNING)
        )
        execution = exec_res.scalar_one_or_none()
        if execution:
            execution.status = ExecutionStatus.FAILED
            execution.finished_at = now
            execution.error = "Worker shutdown gracefully"

    await db.commit()


async def reap_stale_jobs(db: AsyncSession) -> None:
    """Requeue jobs whose worker died (no heartbeat within timeout)."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.STALE_JOB_TIMEOUT_SECONDS)
    res = await db.execute(
        select(Job).where(Job.status == JobStatus.RUNNING, Job.heartbeat_at < cutoff)
    )
    stale_jobs = res.scalars().all()
    if not stale_jobs:
        return

    now = datetime.now(timezone.utc)
    for job in stale_jobs:
        worker_id = job.claimed_by
        job.claimed_by = None
        job.claimed_at = None
        job.heartbeat_at = None

        await transition_job_status(
            db, job, JobStatus.PENDING,
            worker_id=worker_id,
            message=f"Job reaped: worker heartbeat expired (last heartbeat: {job.heartbeat_at})"
        )

        exec_res = await db.execute(
            select(JobExecution)
            .where(JobExecution.job_id == job.id, JobExecution.status == ExecutionStatus.RUNNING)
        )
        execution = exec_res.scalar_one_or_none()
        if execution:
            execution.status = ExecutionStatus.FAILED
            execution.finished_at = now
            execution.error = "Worker heartbeat timeout exceeded"

    await db.commit()


async def claim_jobs(db: AsyncSession, worker_id: uuid.UUID, limit: int) -> list[Job]:
    """Atomically claim up to `limit` jobs, respecting queue pause + concurrency limits.

    Uses FOR UPDATE of queues to prevent race conditions on concurrency limit checks.
    """
    await reap_stale_jobs(db)

    now = datetime.now(timezone.utc)

    # 1. Select candidate queues containing jobs that are ready to be claimed
    candidate_queues_res = await db.execute(
        select(Job.queue_id)
        .where(
            Job.status.in_(CLAIMABLE_STATUSES),
            Job.run_at <= now
        )
        .distinct()
    )
    queue_ids = [row[0] for row in candidate_queues_res.fetchall()]
    if not queue_ids:
        return []

    # 2. Lock candidate queue configurations. Order by ID to prevent deadlocks.
    lock_queues_res = await db.execute(
        select(Queue)
        .where(Queue.id.in_(queue_ids), Queue.is_paused == False)
        .order_by(Queue.id)
        .with_for_update()
    )
    locked_queues = lock_queues_res.scalars().all()
    if not locked_queues:
        return []

    # 3. For each locked queue, calculate capacity
    locked_queue_ids = [q.id for q in locked_queues]
    running_counts_res = await db.execute(
        select(Job.queue_id, func.count(Job.id))
        .where(Job.queue_id.in_(locked_queue_ids), Job.status == JobStatus.RUNNING)
        .group_by(Job.queue_id)
    )
    running_counts = {row[0]: row[1] for row in running_counts_res.fetchall()}

    eligible_queue_limits = {}
    for q in locked_queues:
        current_running = running_counts.get(q.id, 0)
        available = q.max_concurrency - current_running
        if available > 0:
            eligible_queue_limits[q.id] = available

    if not eligible_queue_limits:
        return []

    # 4. Claim eligible jobs queue by queue, honoring concurrency constraints
    claimed_jobs = []
    remaining_limit = limit

    for q_id, q_limit in eligible_queue_limits.items():
        if remaining_limit <= 0:
            break
        q_claim_limit = min(q_limit, remaining_limit)

        # Select jobs from the locked queue using FOR UPDATE SKIP LOCKED
        jobs_res = await db.execute(
            select(Job)
            .where(
                Job.queue_id == q_id,
                Job.status.in_(CLAIMABLE_STATUSES),
                Job.run_at <= now
            )
            .order_by(Job.priority.desc(), Job.run_at.asc())
            .limit(q_claim_limit)
            .with_for_update(skip_locked=True)
        )
        queue_jobs = jobs_res.scalars().all()

        for job in queue_jobs:
            job.claimed_by = worker_id
            job.claimed_at = now
            job.heartbeat_at = now

            await transition_job_status(
                db, job, JobStatus.RUNNING,
                worker_id=worker_id,
                message=f"Job claimed and started execution by worker {worker_id}"
            )

            # Insert execution attempt record
            db.add(JobExecution(
                job_id=job.id,
                worker_id=worker_id,
                attempt=job.retry_count + 1,
                status=ExecutionStatus.RUNNING,
                started_at=now,
            ))

            claimed_jobs.append(job)
            remaining_limit -= 1

    if claimed_jobs:
        await db.commit()
        for job in claimed_jobs:
            await db.refresh(job)

    return claimed_jobs


async def heartbeat(db: AsyncSession, worker_id: uuid.UUID, job_ids: list[uuid.UUID]) -> None:
    now = datetime.now(timezone.utc)
    result = await db.execute(select(Worker).where(Worker.id == worker_id))
    worker = result.scalar_one_or_none()
    if worker:
        worker.last_heartbeat = now
        worker.status = WorkerStatus.ONLINE

        # Log worker heartbeat history record
        db.add(WorkerHeartbeat(
            worker_id=worker_id,
            status=WorkerStatus.ONLINE.value,
            active_jobs=[str(jid) for jid in job_ids],
            metadata_info={"hostname": worker.hostname}
        ))

    if job_ids:
        # Update jobs claimed by this worker
        await db.execute(
            text("UPDATE jobs SET heartbeat_at = :now WHERE id = ANY(:ids) AND claimed_by = :wid"),
            {"now": now, "ids": job_ids, "wid": worker_id},
        )
    await db.commit()


def _compute_retry_delay(job: Job) -> int:
    n = job.retry_count
    if job.retry_strategy == RetryStrategy.FIXED:
        return job.retry_delay_seconds
    if job.retry_strategy == RetryStrategy.LINEAR:
        return job.retry_delay_seconds * (n + 1)
    return job.retry_delay_seconds * (2 ** n)


async def complete_job(
    db: AsyncSession,
    job_id: uuid.UUID,
    worker_id: uuid.UUID,
    success: bool,
    error: str | None,
    logs: str | None,
) -> Job:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.claimed_by != worker_id:
        raise HTTPException(status_code=409, detail="Job not claimed by this worker")

    now = datetime.now(timezone.utc)

    exec_result = await db.execute(
        select(JobExecution)
        .where(JobExecution.job_id == job_id, JobExecution.status == ExecutionStatus.RUNNING)
        .order_by(JobExecution.started_at.desc())
        .limit(1)
    )
    execution = exec_result.scalar_one_or_none()

    if success:
        job.completed_at = now
        job.claimed_by = None
        job.heartbeat_at = None

        if execution:
            execution.status = ExecutionStatus.SUCCEEDED
            execution.finished_at = now
            execution.logs = logs

        await transition_job_status(db, job, JobStatus.SUCCEEDED, worker_id=worker_id, message="Job completed successfully")
    else:
        if execution:
            execution.status = ExecutionStatus.FAILED
            execution.finished_at = now
            execution.error = error
            execution.logs = logs

        if job.retry_count >= job.max_retries:
            job.completed_at = now
            job.claimed_by = None
            job.heartbeat_at = None

            await transition_job_status(db, job, JobStatus.DEAD, worker_id=worker_id, error=error, message="Job execution failed, max retries exceeded")
        else:
            delay = _compute_retry_delay(job)
            job.retry_count += 1
            job.run_at = now + timedelta(seconds=delay)
            job.claimed_by = None
            job.heartbeat_at = None

            await transition_job_status(
                db, job, JobStatus.RETRYING,
                worker_id=worker_id,
                error=error,
                message=f"Job failed, scheduled retry #{job.retry_count} in {delay} seconds"
            )

    await db.commit()
    await db.refresh(job)
    return job


async def list_workers(db: AsyncSession) -> list[Worker]:
    result = await db.execute(select(Worker))
    return result.scalars().all()
