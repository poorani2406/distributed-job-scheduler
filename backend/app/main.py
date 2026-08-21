'''
# backend/app/main.py
from fastapi import FastAPI

app = FastAPI(title="Distributed Job Scheduler")


@app.get("/health")
async def health():
    return {"status": "ok"}
'''
'''
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, projects, queues, jobs, workers


app = FastAPI(title="Distributed Job Scheduler")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(queues.router)
app.include_router(jobs.router)
app.include_router(jobs.batch_router)
app.include_router(jobs.job_router)
app.include_router(workers.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
'''

# UPDATE backend/app/main.py — full replacement
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, projects, queues, jobs, workers, metrics, logs, retry_policies
from app.database import AsyncSessionLocal
from app.services.scheduler_service import scheduler_loop
from app.config import settings
import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):
    import sys
    task = None
    if "pytest" not in sys.modules:
        task = asyncio.create_task(scheduler_loop(AsyncSessionLocal, interval_seconds=5.0))
    yield
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Distributed Job Scheduler", lifespan=lifespan)

cors_origins_str = settings.CORS_ORIGINS
if cors_origins_str == "*":
    origins = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]
else:
    origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(projects.org_router)
app.include_router(queues.router)
app.include_router(queues.flat_router)
app.include_router(jobs.router)
app.include_router(jobs.batch_router)
app.include_router(jobs.job_router)
app.include_router(workers.router)
app.include_router(metrics.router)
app.include_router(logs.router)
app.include_router(retry_policies.router)
app.include_router(retry_policies.flat_router)


@app.get("/health")
async def health():
    return {"status": "ok"}