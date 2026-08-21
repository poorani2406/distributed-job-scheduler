# backend/app/models/user.py
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    #role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), default=UserRole.MEMBER)
    
    role: Mapped[UserRole] = mapped_column(
    Enum(
        UserRole,
        name="user_role",
        values_callable=lambda x: [e.value for e in x]
    ),
    default=UserRole.MEMBER
)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped["Organization"] = relationship(back_populates="users")
