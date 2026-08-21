# backend/app/routers/retry_policies.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas import RetryPolicyCreate, RetryPolicyOut
from app.security import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.retry_policy import RetryPolicy

router = APIRouter(prefix="/api/projects/{project_id}/retry-policies", tags=["retry_policies"])
flat_router = APIRouter(prefix="/api/retry-policies", tags=["retry_policies"])


async def _get_project(db: AsyncSession, project_id: uuid.UUID, org_id: uuid.UUID) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id, Project.org_id == org_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("", response_model=RetryPolicyOut)
async def create_retry_policy(
    project_id: uuid.UUID,
    data: RetryPolicyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    await _get_project(db, project_id, user.org_id)
    policy = RetryPolicy(
        project_id=project_id,
        name=data.name,
        strategy=data.strategy,
        max_retries=data.max_retries,
        delay_seconds=data.delay_seconds
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy


@router.get("", response_model=list[RetryPolicyOut])
async def list_retry_policies(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    await _get_project(db, project_id, user.org_id)
    result = await db.execute(select(RetryPolicy).where(RetryPolicy.project_id == project_id))
    return result.scalars().all()


@flat_router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_retry_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(RetryPolicy).join(RetryPolicy.project).where(RetryPolicy.id == policy_id, Project.org_id == user.org_id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Retry policy not found")
    await db.delete(policy)
    await db.commit()
    return None
