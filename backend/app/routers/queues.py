# backend/app/routers/queues.py
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas import QueueCreate, QueueOut, QueueUpdate, QueueDetailOut, QueueStatsOut
from app.security import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.queue import Queue
from app.models.job import Job, JobStatus

router = APIRouter(prefix="/api/projects/{project_id}/queues", tags=["queues"])
flat_router = APIRouter(prefix="/api/queues", tags=["queues"])


async def _get_project(db: AsyncSession, project_id: uuid.UUID, org_id: uuid.UUID) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id, Project.org_id == org_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _get_queue_by_id(db: AsyncSession, queue_id: uuid.UUID, org_id: uuid.UUID) -> Queue:
    result = await db.execute(
        select(Queue).join(Queue.project).where(Queue.id == queue_id, Project.org_id == org_id)
    )
    queue = result.scalar_one_or_none()
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    return queue


async def _calculate_queue_stats(db: AsyncSession, queue_id: uuid.UUID) -> QueueStatsOut:
    result = await db.execute(
        select(Job.status, func.count(Job.id))
        .where(Job.queue_id == queue_id)
        .group_by(Job.status)
    )
    counts = {row[0]: row[1] for row in result.fetchall()}
    
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    throughput_res = await db.execute(
        select(func.count(Job.id))
        .where(Job.queue_id == queue_id, Job.status == JobStatus.SUCCEEDED, Job.completed_at >= since)
    )
    throughput = throughput_res.scalar_one()

    return QueueStatsOut(
        queued=counts.get(JobStatus.PENDING, 0),
        scheduled=counts.get(JobStatus.SCHEDULED, 0),
        running=counts.get(JobStatus.RUNNING, 0),
        completed=counts.get(JobStatus.SUCCEEDED, 0),
        failed=counts.get(JobStatus.FAILED, 0),
        retrying=counts.get(JobStatus.RETRYING, 0),
        dlq=counts.get(JobStatus.DEAD, 0),
        cancelled=counts.get(JobStatus.CANCELLED, 0),
        throughput=throughput,
    )


# ---- Project-Nested Queue Endpoints ----

@router.post("", response_model=QueueOut)
async def create_queue(
    project_id: uuid.UUID,
    data: QueueCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    await _get_project(db, project_id, user.org_id)
    queue = Queue(
        project_id=project_id,
        name=data.name,
        description=data.description,
        priority=data.priority,
        max_concurrency=data.max_concurrency,
        retry_policy_id=data.retry_policy_id
    )
    db.add(queue)
    await db.commit()
    await db.refresh(queue)
    return queue


@router.get("", response_model=list[QueueDetailOut])
async def list_queues(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    await _get_project(db, project_id, user.org_id)
    result = await db.execute(select(Queue).where(Queue.project_id == project_id))
    queues = result.scalars().all()
    
    details = []
    for q in queues:
        stats = await _calculate_queue_stats(db, q.id)
        details.append(QueueDetailOut(
            id=q.id,
            project_id=q.project_id,
            name=q.name,
            description=q.description,
            priority=q.priority,
            max_concurrency=q.max_concurrency,
            is_paused=q.is_paused,
            retry_policy_id=q.retry_policy_id,
            created_at=q.created_at,
            stats=stats
        ))
    return details


@router.patch("/{queue_id}", response_model=QueueOut)
async def update_queue_nested(
    project_id: uuid.UUID,
    queue_id: uuid.UUID,
    data: QueueUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    await _get_project(db, project_id, user.org_id)
    queue = await _get_queue_by_id(db, queue_id, user.org_id)
    if data.description is not None:
        queue.description = data.description
    if data.priority is not None:
        queue.priority = data.priority
    if data.max_concurrency is not None:
        queue.max_concurrency = data.max_concurrency
    if data.is_paused is not None:
        queue.is_paused = data.is_paused
    if data.retry_policy_id is not None:
        queue.retry_policy_id = data.retry_policy_id
        
    await db.commit()
    await db.refresh(queue)
    return queue


@router.post("/{queue_id}/pause", response_model=QueueOut)
async def pause_queue_nested(
    project_id: uuid.UUID,
    queue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    await _get_project(db, project_id, user.org_id)
    queue = await _get_queue_by_id(db, queue_id, user.org_id)
    queue.is_paused = True
    await db.commit()
    await db.refresh(queue)
    return queue


@router.post("/{queue_id}/resume", response_model=QueueOut)
async def resume_queue_nested(
    project_id: uuid.UUID,
    queue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    await _get_project(db, project_id, user.org_id)
    queue = await _get_queue_by_id(db, queue_id, user.org_id)
    queue.is_paused = False
    await db.commit()
    await db.refresh(queue)
    return queue


# ---- Flat Queue Endpoints ----

@flat_router.get("/{queue_id}", response_model=QueueDetailOut)
async def get_queue_flat(
    queue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    queue = await _get_queue_by_id(db, queue_id, user.org_id)
    stats = await _calculate_queue_stats(db, queue.id)
    return QueueDetailOut(
        id=queue.id,
        project_id=queue.project_id,
        name=queue.name,
        description=queue.description,
        priority=queue.priority,
        max_concurrency=queue.max_concurrency,
        is_paused=queue.is_paused,
        retry_policy_id=queue.retry_policy_id,
        created_at=queue.created_at,
        stats=stats
    )


@flat_router.patch("/{queue_id}", response_model=QueueOut)
async def update_queue_flat(
    queue_id: uuid.UUID,
    data: QueueUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    queue = await _get_queue_by_id(db, queue_id, user.org_id)
    if data.description is not None:
        queue.description = data.description
    if data.priority is not None:
        queue.priority = data.priority
    if data.max_concurrency is not None:
        queue.max_concurrency = data.max_concurrency
    if data.is_paused is not None:
        queue.is_paused = data.is_paused
    if data.retry_policy_id is not None:
        queue.retry_policy_id = data.retry_policy_id
        
    await db.commit()
    await db.refresh(queue)
    return queue


@flat_router.delete("/{queue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_queue_flat(
    queue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    queue = await _get_queue_by_id(db, queue_id, user.org_id)
    await db.delete(queue)
    await db.commit()
    return None


@flat_router.post("/{queue_id}/pause", response_model=QueueOut)
async def pause_queue_flat(
    queue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    queue = await _get_queue_by_id(db, queue_id, user.org_id)
    queue.is_paused = True
    await db.commit()
    await db.refresh(queue)
    return queue


@flat_router.post("/{queue_id}/resume", response_model=QueueOut)
async def resume_queue_flat(
    queue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    queue = await _get_queue_by_id(db, queue_id, user.org_id)
    queue.is_paused = False
    await db.commit()
    await db.refresh(queue)
    return queue