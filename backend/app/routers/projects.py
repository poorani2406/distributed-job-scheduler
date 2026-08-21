# backend/app/routers/projects.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas import ProjectCreate, ProjectOut, ProjectUpdate, OrganizationCreate, OrganizationOut
from app.security import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.organization import Organization

router = APIRouter(prefix="/api/projects", tags=["projects"])
org_router = APIRouter(prefix="/api/organizations", tags=["organizations"])


@org_router.post("", response_model=OrganizationOut)
async def create_organization(data: OrganizationCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    org = Organization(name=data.name)
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


@router.post("", response_model=ProjectOut)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    project = Project(org_id=user.org_id, name=data.name)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
async def list_projects(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Project).where(Project.org_id == user.org_id))
    return result.scalars().all()


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.org_id == user.org_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(project_id: uuid.UUID, data: ProjectUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.org_id == user.org_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if data.name is not None:
        project.name = data.name
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}")
async def delete_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.org_id == user.org_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    await db.commit()
    return {"detail": "Project deleted successfully"}