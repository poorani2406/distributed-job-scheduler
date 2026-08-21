# backend/app/services/auth_service.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.user import User
from app.models.organization import Organization
from app.schemas import UserRegister
from app.security import hash_password, verify_password
from app.models.user import User,UserRole

async def register_user(db: AsyncSession, data: UserRegister) -> User:
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    org = Organization(name=data.org_name)
    db.add(org)
    await db.flush()

    user = User(
        org_id=org.id,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=UserRole.ADMIN,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return user