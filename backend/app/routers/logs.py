# backend/app/routers/logs.py
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.security import get_current_user
from app.models.user import User
from app.schemas import ExecutionOut

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/recent", response_model=list[ExecutionOut])
async def recent_executions(
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        text("""
            SELECT je.id, je.job_id, je.worker_id, je.attempt, je.status,
                   je.started_at, je.finished_at, je.error, je.logs
            FROM job_executions je
            JOIN jobs j ON j.id = je.job_id
            JOIN queues q ON q.id = j.queue_id
            JOIN projects p ON p.id = q.project_id
            WHERE p.org_id = :org_id
            ORDER BY je.started_at DESC
            LIMIT :limit
        """),
        {"org_id": user.org_id, "limit": limit},
    )
    rows = result.fetchall()
    return [
        {
            "id": r[0], "job_id": r[1], "worker_id": r[2], "attempt": r[3],
            "status": r[4], "started_at": r[5], "finished_at": r[6],
            "error": r[7], "logs": r[8],
        }
        for r in rows
    ]