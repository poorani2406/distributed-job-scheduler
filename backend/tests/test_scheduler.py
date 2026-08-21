# backend/tests/test_scheduler.py
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from tests.conftest import TestSessionLocal
from app.models.job import Job, JobStatus
from app.services.scheduler_service import process_recurring_jobs

@pytest.mark.asyncio
async def test_scheduler_concurrency(auth_client):
    # 1. Setup a project and queue
    r = await auth_client.post("/api/projects", json={"name": "Scheduler Test Proj"})
    assert r.status_code == 200
    proj_id = r.json()["id"]

    r = await auth_client.post(f"/api/projects/{proj_id}/queues", json={"name": "scheduler_q", "max_concurrency": 2})
    assert r.status_code == 200
    queue_id = r.json()["id"]

    # 2. Submit a recurring job template (immediate fire triggers cron calculation)
    r = await auth_client.post(
        f"/api/queues/{queue_id}/jobs",
        json={
            "name": "recurring_task",
            "cron_expression": "*/5 * * * *",
        }
    )
    assert r.status_code == 200
    tmpl_id = r.json()["id"]

    # 3. Manually update the template job in the DB to be COMPLETED and DUE in the past
    async with TestSessionLocal() as db:
        res = await db.execute(select(Job).where(Job.id == tmpl_id))
        job = res.scalar_one()
        job.status = JobStatus.SUCCEEDED
        job.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        await db.commit()

    # 4. Spin up two scheduler instances polling process_recurring_jobs concurrently
    # using two separate DB sessions simulating two replicas.
    async def run_scheduler():
        async with TestSessionLocal() as db:
            return await process_recurring_jobs(db)

    # Execute concurrently
    results = await asyncio.gather(run_scheduler(), run_scheduler())

    # 5. Assertions
    # One instance must have returned 1 (spawned a job), the other must have returned 0 (skipped/prevented duplicate)
    assert sum(results) == 1
    assert 1 in results
    assert 0 in results

    # 6. Verify database records
    async with TestSessionLocal() as db:
        # Check total jobs in the queue: should be exactly 2 (the original template, plus the 1 new spawned run)
        res = await db.execute(select(Job).where(Job.queue_id == queue_id))
        jobs = res.scalars().all()
        assert len(jobs) == 2

        # Verify next_run_at of the original template is consumed (None)
        res = await db.execute(select(Job).where(Job.id == tmpl_id))
        tmpl_job = res.scalar_one()
        assert tmpl_job.next_run_at is None

        # Verify the newly spawned job has the correct unique idempotency key
        spawned_job = [j for j in jobs if j.id != tmpl_job.id][0]
        assert spawned_job.idempotency_key == f"cron-{tmpl_job.id}-{spawned_job.run_at.isoformat()}"
        assert spawned_job.status == JobStatus.SCHEDULED
