# backend/tests/test_worker_claim.py
import asyncio
import pytest

pytestmark = pytest.mark.asyncio


async def test_atomic_claim_respects_concurrency_limit(auth_client):
    r = await auth_client.post("/api/projects", json={"name": "P"})
    project_id = r.json()["id"]
    r = await auth_client.post(f"/api/projects/{project_id}/queues", json={"name": "Q", "max_concurrency": 1})
    queue_id = r.json()["id"]

    for _ in range(3):
        await auth_client.post(f"/api/queues/{queue_id}/jobs", json={"name": "default"})

    r = await auth_client.post("/api/workers/register", json={"hostname": "w1", "concurrency": 5})
    worker_id = r.json()["id"]

    r = await auth_client.post("/api/workers/claim", json={"worker_id": worker_id, "limit": 5})
    claimed = r.json()
    # only 1 job claimed because max_concurrency=1 and nothing has completed yet
    assert len(claimed) == 1

    r = await auth_client.post("/api/workers/claim", json={"worker_id": worker_id, "limit": 5})
    assert len(r.json()) == 0


async def test_retry_and_dlq_flow(auth_client):
    r = await auth_client.post("/api/projects", json={"name": "P"})
    project_id = r.json()["id"]
    r = await auth_client.post(f"/api/projects/{project_id}/queues", json={"name": "Q", "max_concurrency": 5})
    queue_id = r.json()["id"]

    r = await auth_client.post(f"/api/queues/{queue_id}/jobs", json={
        "name": "default", "max_retries": 1, "retry_strategy": "fixed", "retry_delay_seconds": 0
    })
    job_id = r.json()["id"]

    r = await auth_client.post("/api/workers/register", json={"hostname": "w1", "concurrency": 5})
    worker_id = r.json()["id"]

    # attempt 1: fail -> retrying
    await auth_client.post("/api/workers/claim", json={"worker_id": worker_id, "limit": 5})
    r = await auth_client.post(f"/api/jobs/{job_id}/complete", json={
        "worker_id": worker_id, "success": False, "error": "boom"
    })
    assert r.json()["status"] == "retrying"

    # attempt 2: fail -> exceeds max_retries=1 -> dead (DLQ)
    await asyncio.sleep(0.1)
    await auth_client.post("/api/workers/claim", json={"worker_id": worker_id, "limit": 5})
    r = await auth_client.post(f"/api/jobs/{job_id}/complete", json={
        "worker_id": worker_id, "success": False, "error": "boom again"
    })
    assert r.json()["status"] == "dead"

    r = await auth_client.post(f"/api/jobs/{job_id}/retry")
    assert r.json()["status"] == "pending"


async def test_multiple_workers_competing_claim(auth_client):
    r = await auth_client.post("/api/projects", json={"name": "P_compete"})
    project_id = r.json()["id"]
    r = await auth_client.post(f"/api/projects/{project_id}/queues", json={"name": "Q_compete", "max_concurrency": 10})
    queue_id = r.json()["id"]

    for i in range(10):
        await auth_client.post(f"/api/queues/{queue_id}/jobs", json={"name": f"job_{i}"})

    worker_ids = []
    for i in range(3):
        rw = await auth_client.post("/api/workers/register", json={"hostname": f"w_{i}", "concurrency": 5})
        worker_ids.append(rw.json()["id"])

    async def claim_task(w_id):
        resp = await auth_client.post("/api/workers/claim", json={"worker_id": w_id, "limit": 5})
        return resp.json()

    results = await asyncio.gather(*(claim_task(wid) for wid in worker_ids))

    claimed_job_ids = []
    for claimed_list in results:
        for job in claimed_list:
            claimed_job_ids.append(job["id"])

    assert len(claimed_job_ids) == len(set(claimed_job_ids))
    assert len(claimed_job_ids) <= 10
