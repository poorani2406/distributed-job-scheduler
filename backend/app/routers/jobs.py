# backend/app/routers/jobs.py
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.schemas import JobCreate, JobOut, BatchJobCreate, BatchOut, ExecutionOut, JobLogOut, JobCompleteRequest
from app.security import get_current_user
from app.models.user import User
from app.models.job import Job, JobStatus
from app.models.queue import Queue
from app.models.project import Project
from app.models.log import JobLog
from app.services.job_service import get_owned_queue, create_job, create_batch_jobs, cancel_job, retry_dead_job
from app.services import worker_service

router = APIRouter(prefix="/api/queues/{queue_id}/jobs", tags=["jobs"])
batch_router = APIRouter(prefix="/api/projects/{project_id}/queues/{queue_id}/batches", tags=["batches"])
job_router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("", response_model=JobOut)
async def submit_job(queue_id: uuid.UUID, data: JobCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_owned_queue(db, queue_id, user.org_id)
    return await create_job(db, queue_id, data)


@router.get("", response_model=list[JobOut])
async def list_jobs(
    queue_id: uuid.UUID,
    status_filter: JobStatus | None = Query(default=None, alias="status"),
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await get_owned_queue(db, queue_id, user.org_id)
    stmt = select(Job).where(Job.queue_id == queue_id)
    if status_filter:
        stmt = stmt.where(Job.status == status_filter)
    stmt = stmt.order_by(Job.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@batch_router.post("", response_model=BatchOut)
async def submit_batch(
    project_id: uuid.UUID,
    queue_id: uuid.UUID,
    data: BatchJobCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await get_owned_queue(db, queue_id, user.org_id)
    return await create_batch_jobs(db, project_id, queue_id, data)


async def _get_owned_job(db: AsyncSession, job_id: uuid.UUID, org_id: uuid.UUID) -> Job:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await get_owned_queue(db, job.queue_id, org_id)  # raises 404 if not owned
    return job


@job_router.get("/dlq", response_model=list[JobOut])
async def list_dlq_jobs(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    stmt = (
        select(Job)
        .join(Queue)
        .join(Project)
        .where(Project.org_id == user.org_id, Job.status == JobStatus.DEAD)
        .order_by(Job.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@job_router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await _get_owned_job(db, job_id, user.org_id)


@job_router.get("/{job_id}/executions", response_model=list[ExecutionOut])
async def get_job_executions(job_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    job = await _get_owned_job(db, job_id, user.org_id)
    result = await db.execute(
        select(Job).options(selectinload(Job.executions)).where(Job.id == job.id)
    )
    return result.scalar_one().executions


@job_router.get("/{job_id}/logs", response_model=list[JobLogOut])
async def get_job_logs(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    await _get_owned_job(db, job_id, user.org_id)
    result = await db.execute(
        select(JobLog).where(JobLog.job_id == job_id).order_by(JobLog.created_at.asc())
    )
    return result.scalars().all()


@job_router.post("/{job_id}/cancel", response_model=JobOut)
async def cancel(job_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    job = await _get_owned_job(db, job_id, user.org_id)
    return await cancel_job(db, job)


@job_router.post("/{job_id}/retry", response_model=JobOut)
async def retry(job_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    job = await _get_owned_job(db, job_id, user.org_id)
    return await retry_dead_job(db, job)


@job_router.post("/{job_id}/complete", response_model=JobOut)
async def complete_job(job_id: uuid.UUID, data: JobCompleteRequest, db: AsyncSession = Depends(get_db)):
    return await worker_service.complete_job(db, job_id, data.worker_id, data.success, data.error, data.logs)