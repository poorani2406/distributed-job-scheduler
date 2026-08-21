import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://backend:8000")
    WORKER_CONCURRENCY: int = 4
    WORKER_POLL_INTERVAL_SECONDS: float = 1.0
    HEARTBEAT_INTERVAL_SECONDS: float = 5.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = WorkerSettings()