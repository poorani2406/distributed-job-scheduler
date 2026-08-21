# backend/app/routers/metrics.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.security import get_current_user
from app.models.user import User
from app.services.metrics_service import get_org_metrics

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("")
async def metrics(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await get_org_metrics(db, user.org_id)