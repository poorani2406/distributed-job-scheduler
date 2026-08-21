# backend/tests/test_jobs.py
import pytest

pytestmark = pytest.mark.asyncio


async def _setup_queue(auth_client):
    r = await auth_client.post("/api/projects", json={"name": "P1"})
    project_id = r.json()["id"]
    r = await auth_client.post(f"/api/projects/{project_id}/queues", json={"name": "Q1", "max_concurrency": 2})
    queue_id = r.json()["id"]
    return project_id, queue_id


async def test_create_and_list_jobs(auth_client):
    _, queue_id = await _setup_queue(auth_client)
    r = await auth_client.post(f"/api/queues/{queue_id}/jobs", json={"name": "default", "payload": {"x": 1}})
    assert r.status_code == 200
    job = r.json()
    assert job["status"] == "pending"

    r = await auth_client.get(f"/api/queues/{queue_id}/jobs")
    assert len(r.json()) == 1


async def test_delayed_job_scheduled_status(auth_client):
    _, queue_id = await _setup_queue(auth_client)
    r = await auth_client.post(f"/api/queues/{queue_id}/jobs", json={
        "name": "default", "run_at": "2099-01-01T00:00:00Z"
    })
    assert r.json()["status"] == "scheduled"


async def test_cancel_job(auth_client):
    _, queue_id = await _setup_queue(auth_client)
    r = await auth_client.post(f"/api/queues/{queue_id}/jobs", json={"name": "default"})
    job_id = r.json()["id"]
    r = await auth_client.post(f"/api/jobs/{job_id}/cancel")
    assert r.json()["status"] == "cancelled"

    r = await auth_client.post(f"/api/jobs/{job_id}/cancel")
    assert r.status_code == 400


async def test_batch_job_creation(auth_client):
    project_id, queue_id = await _setup_queue(auth_client)
    r = await auth_client.post(f"/api/projects/{project_id}/queues/{queue_id}/batches", json={
        "batch_name": "b1",
        "jobs": [{"name": "default"}, {"name": "default"}, {"name": "default"}],
    })
    assert r.status_code == 200
    assert len(r.json()["jobs"]) == 3


async def test_queue_pause_blocks_claiming(auth_client):
    project_id, queue_id = await _setup_queue(auth_client)
    await auth_client.post(f"/api/queues/{queue_id}/jobs", json={"name": "default"})
    await auth_client.post(f"/api/projects/{project_id}/queues/{queue_id}/pause")

    r = await auth_client.post("/api/workers/register", json={"hostname": "w1", "concurrency": 2})
    worker_id = r.json()["id"]
    r = await auth_client.post("/api/workers/claim", json={"worker_id": worker_id, "limit": 5})
    assert r.json() == []