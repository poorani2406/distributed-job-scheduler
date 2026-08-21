# backend/app/routers/workers.py
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas import (
    WorkerRegister, WorkerOut, ClaimRequest, JobOut,
    HeartbeatRequest, JobCompleteRequest,
)
from app.services import worker_service

router = APIRouter(prefix="/api/workers", tags=["workers"])


@router.post("/register", response_model=WorkerOut)
async def register(data: WorkerRegister, db: AsyncSession = Depends(get_db)):
    return await worker_service.register_worker(db, data.hostname, data.concurrency)


@router.get("", response_model=list[WorkerOut])
async def list_workers(db: AsyncSession = Depends(get_db)):
    return await worker_service.list_workers(db)


@router.post("/claim", response_model=list[JobOut])
async def claim(data: ClaimRequest, db: AsyncSession = Depends(get_db)):
    return await worker_service.claim_jobs(db, data.worker_id, data.limit)


@router.post("/heartbeat")
async def send_heartbeat(data: HeartbeatRequest, db: AsyncSession = Depends(get_db)):
    await worker_service.heartbeat(db, data.worker_id, data.job_ids)
    return {"status": "ok"}


@router.post("/{worker_id}/deregister")
async def deregister(worker_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await worker_service.deregister_worker(db, worker_id)
    return {"status": "ok"}
