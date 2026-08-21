# backend/app/services/scheduler_service.py
import logging
from datetime import datetime, timezone
from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.job import Job, JobStatus
from app.models.log import JobLog
from app.models.scheduled_job import ScheduledJob

log = logging.getLogger("scheduler")

async def process_recurring_jobs(db: AsyncSession) -> int:
    """Find completed cron jobs whose next occurrence is due and spawn the next run.

    A job with cron_expression set acts as a template: each time an instance
    reaches a terminal state (succeeded/failed/dead/cancelled), we compute the
    next fire time and insert a fresh PENDING/SCHEDULED job row.
    """
    from sqlalchemy.exc import IntegrityError

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Job).where(
            Job.cron_expression.isnot(None),
            Job.status.in_([JobStatus.SUCCEEDED.value, JobStatus.FAILED.value, JobStatus.DEAD.value, JobStatus.CANCELLED.value]),
            Job.next_run_at.isnot(None),
            Job.next_run_at <= now,
        )
        .order_by(Job.id)
        .with_for_update(skip_locked=True)
    )
    templates = result.scalars().all()
    spawned = 0

    for tmpl in templates:
        occurrence_time = tmpl.next_run_at
        try:
            async with db.begin_nested():
                cron = croniter(tmpl.cron_expression, now)
                next_fire = cron.get_next(datetime)

                new_job = Job(
                    queue_id=tmpl.queue_id,
                    batch_id=tmpl.batch_id,
                    name=tmpl.name,
                    payload=tmpl.payload,
                    priority=tmpl.priority,
                    run_at=occurrence_time,
                    status=JobStatus.SCHEDULED,
                    timeout_seconds=tmpl.timeout_seconds,
                    max_retries=tmpl.max_retries,
                    retry_strategy=tmpl.retry_strategy,
                    retry_delay_seconds=tmpl.retry_delay_seconds,
                    cron_expression=tmpl.cron_expression,
                    next_run_at=next_fire,
                    idempotency_key=f"cron-{tmpl.id}-{occurrence_time.isoformat()}",
                )
                db.add(new_job)
                await db.flush()

                # Log creation of the new run
                db.add(JobLog(
                    job_id=new_job.id,
                    event="JOB_CREATED",
                    message=f"Recurring cron instance spawned from job {tmpl.id}",
                    created_at=now
                ))

                # Insert scheduled_jobs tracking entry
                db.add(ScheduledJob(
                    job_id=new_job.id,
                    run_at=new_job.run_at,
                    cron_expression=new_job.cron_expression
                ))

                tmpl.next_run_at = None  # this template instance is now consumed
                spawned += 1
        except IntegrityError:
            log.warning(f"Duplicate recurring job spawn prevented via idempotency key for job {tmpl.id} at {occurrence_time}")
        except Exception as e:
            log.error(f"Failed to spawn cron run for job {tmpl.id}: {e}")

    if spawned or templates:
        await db.commit()
        if spawned:
            log.info(f"Spawned {spawned} recurring job instance(s)")
    return spawned


async def scheduler_loop(session_factory, interval_seconds: float = 5.0):
    import asyncio
    while True:
        try:
            async with session_factory() as db:
                await process_recurring_jobs(db)
        except Exception as e:
            log.error(f"Scheduler loop error: {e}")
        await asyncio.sleep(interval_seconds)