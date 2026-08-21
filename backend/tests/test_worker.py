# backend/tests/test_worker.py
import pytest

async def test_worker_lifecycle_and_heartbeat(auth_client):
    # 1. Register worker
    r = await auth_client.post("/api/workers/register", json={"hostname": "node-1", "concurrency": 4})
    assert r.status_code == 200
    worker_id = r.json()["id"]
    assert r.json()["hostname"] == "node-1"
    assert r.json()["status"] == "online"

    # 2. Verify in list
    r = await auth_client.get("/api/workers")
    assert r.status_code == 200
    hostnames = [w["hostname"] for w in r.json()]
    assert "node-1" in hostnames

    # 3. Setup project, queue, and job to claim
    r = await auth_client.post("/api/projects", json={"name": "Worker test proj"})
    proj_id = r.json()["id"]
    r = await auth_client.post(f"/api/projects/{proj_id}/queues", json={"name": "worker_q", "max_concurrency": 2})
    queue_id = r.json()["id"]
    r = await auth_client.post(f"/api/queues/{queue_id}/jobs", json={"name": "worker_job"})
    job_id = r.json()["id"]

    # 4. Claim the job (moves status to running)
    r = await auth_client.post("/api/workers/claim", json={"worker_id": worker_id, "limit": 2})
    assert len(r.json()) == 1
    assert r.json()[0]["id"] == job_id

    # 5. Heartbeat updates last_heartbeat and registers heartbeat log
    r = await auth_client.post("/api/workers/heartbeat", json={"worker_id": worker_id, "job_ids": [job_id]})
    assert r.status_code == 200

    # 6. Graceful Deregistration/shutdown releases claimed jobs
    r = await auth_client.post(f"/api/workers/{worker_id}/deregister")
    assert r.status_code == 200

    # 7. Verify job is returned to pending
    r = await auth_client.get(f"/api/jobs/{job_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
    assert r.json()["claimed_by"] is None
