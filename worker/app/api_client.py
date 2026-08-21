# worker/app/api_client.py
import uuid
import httpx
from app.config import settings


class ApiClient:
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=settings.API_BASE_URL, timeout=30.0)

    async def register(self, hostname: str, concurrency: int) -> dict:
        r = await self.client.post("/api/workers/register", json={"hostname": hostname, "concurrency": concurrency})
        r.raise_for_status()
        return r.json()

    async def claim(self, worker_id: str, limit: int) -> list[dict]:
        r = await self.client.post("/api/workers/claim", json={"worker_id": worker_id, "limit": limit})
        r.raise_for_status()
        return r.json()

    async def heartbeat(self, worker_id: str, job_ids: list[str]) -> None:
        await self.client.post("/api/workers/heartbeat", json={"worker_id": worker_id, "job_ids": job_ids})

    async def complete(self, job_id: str, worker_id: str, success: bool, error: str | None, logs: str | None) -> None:
        await self.client.post(
            f"/api/jobs/{job_id}/complete",
            json={"worker_id": worker_id, "success": success, "error": error, "logs": logs},
        )

    async def deregister(self, worker_id: str) -> None:
        try:
            await self.client.post(f"/api/workers/{worker_id}/deregister")
        except Exception:
            pass

    async def close(self):
        await self.client.aclose()