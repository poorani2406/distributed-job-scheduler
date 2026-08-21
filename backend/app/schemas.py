# backend/app/schemas.py
import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from app.models.job import JobStatus, RetryStrategy


# ---- Auth ----
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    org_name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    org_id: uuid.UUID
    role: str

    class Config:
        from_attributes = True


# ---- Organization ----
class OrganizationCreate(BaseModel):
    name: str


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Project ----
class ProjectCreate(BaseModel):
    name: str


class ProjectUpdate(BaseModel):
    name: str | None = None


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Retry Policy ----
class RetryPolicyCreate(BaseModel):
    name: str
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    max_retries: int = 3
    delay_seconds: int = 10


class RetryPolicyOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    strategy: str
    max_retries: int
    delay_seconds: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Queue ----
class QueueCreate(BaseModel):
    name: str
    description: str | None = None
    priority: int = 0
    max_concurrency: int = 5
    retry_policy_id: uuid.UUID | None = None


class QueueUpdate(BaseModel):
    description: str | None = None
    priority: int | None = None
    max_concurrency: int | None = None
    is_paused: bool | None = None
    retry_policy_id: uuid.UUID | None = None


class QueueOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    priority: int
    max_concurrency: int
    is_paused: bool
    retry_policy_id: uuid.UUID | None
    created_at: datetime

    class Config:
        from_attributes = True


class QueueStatsOut(BaseModel):
    queued: int
    scheduled: int
    running: int
    completed: int
    failed: int
    retrying: int
    dlq: int
    cancelled: int
    throughput: int


class QueueDetailOut(QueueOut):
    stats: QueueStatsOut | None = None


# ---- Job ----
class JobCreate(BaseModel):
    name: str
    payload: dict = {}
    priority: int = 0
    job_type: str | None = None  # immediate, delayed, scheduled, cron
    delay_seconds: int | None = None
    run_at: datetime | None = None
    timeout_seconds: int = 300
    max_retries: int = 3
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    retry_delay_seconds: int = 10
    cron_expression: str | None = None
    idempotency_key: str | None = None


class BatchJobCreate(BaseModel):
    batch_name: str | None = None
    jobs: list[JobCreate]


class JobOut(BaseModel):
    id: uuid.UUID
    queue_id: uuid.UUID
    batch_id: uuid.UUID | None
    name: str
    payload: dict
    status: JobStatus
    priority: int
    run_at: datetime
    timeout_seconds: int
    max_retries: int
    retry_count: int
    retry_strategy: RetryStrategy
    retry_delay_seconds: int
    cron_expression: str | None
    next_run_at: datetime | None
    claimed_by: uuid.UUID | None
    idempotency_key: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


class BatchOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str | None
    created_at: datetime
    jobs: list[JobOut] = []

    class Config:
        from_attributes = True


# ---- Execution ----
class ExecutionOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    worker_id: uuid.UUID | None
    attempt: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    error: str | None
    logs: str | None

    class Config:
        from_attributes = True


# ---- Job Logs ----
class JobLogOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    worker_id: uuid.UUID | None
    event: str
    message: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Worker claiming (used by worker service) ----
class ClaimRequest(BaseModel):
    worker_id: uuid.UUID
    queue_names: list[str] | None = None
    limit: int = 1


class HeartbeatRequest(BaseModel):
    worker_id: uuid.UUID
    job_ids: list[uuid.UUID] = []


class JobCompleteRequest(BaseModel):
    worker_id: uuid.UUID
    success: bool
    error: str | None = None
    logs: str | None = None


class WorkerRegister(BaseModel):
    hostname: str
    concurrency: int = 4


class WorkerOut(BaseModel):
    id: uuid.UUID
    hostname: str
    status: str
    concurrency: int
    started_at: datetime
    last_heartbeat: datetime

    class Config:
        from_attributes = True