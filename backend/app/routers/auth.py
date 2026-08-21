# backend/app/routers/auth.py
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas import UserRegister, Token, UserOut
from app.services.auth_service import register_user, authenticate_user
from app.security import create_access_token, get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=Token)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    user = await register_user(db, data)
    token = create_access_token(str(user.id))
    return Token(access_token=token)


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, form_data.username, form_data.password)
    token = create_access_token(str(user.id))
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user