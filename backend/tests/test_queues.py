# backend/tests/test_queues.py
import pytest

async def test_queue_crud_and_pause_resume(auth_client):
    # 1. Setup project
    r = await auth_client.post("/api/projects", json={"name": "Project for Queues"})
    project_id = r.json()["id"]

    # 2. Setup retry policy
    r = await auth_client.post(
        f"/api/projects/{project_id}/retry-policies",
        json={"name": "RP1", "strategy": "linear", "max_retries": 5, "delay_seconds": 15}
    )
    rp_id = r.json()["id"]

    # 3. Create queue inside project, attaching retry policy
    r = await auth_client.post(
        f"/api/projects/{project_id}/queues",
        json={
            "name": "Queue1",
            "description": "Primary task queue",
            "priority": 10,
            "max_concurrency": 3,
            "retry_policy_id": rp_id
        }
    )
    assert r.status_code == 200
    queue_id = r.json()["id"]
    assert r.json()["name"] == "Queue1"
    assert r.json()["description"] == "Primary task queue"
    assert r.json()["priority"] == 10
    assert r.json()["max_concurrency"] == 3
    assert r.json()["retry_policy_id"] == rp_id

    # 4. Get flat queue
    r = await auth_client.get(f"/api/queues/{queue_id}")
    assert r.status_code == 200
    assert r.json()["name"] == "Queue1"

    # 5. Patch flat queue
    r = await auth_client.patch(
        f"/api/queues/{queue_id}",
        json={"description": "Updated description", "max_concurrency": 4}
    )
    assert r.status_code == 200
    assert r.json()["description"] == "Updated description"
    assert r.json()["max_concurrency"] == 4

    # 6. Pause queue
    r = await auth_client.post(f"/api/queues/{queue_id}/pause")
    assert r.status_code == 200
    assert r.json()["is_paused"] is True

    # 7. Resume queue
    r = await auth_client.post(f"/api/queues/{queue_id}/resume")
    assert r.status_code == 200
    assert r.json()["is_paused"] is False

    # 8. Queue stats (inline in detail GET)
    r = await auth_client.get(f"/api/queues/{queue_id}")
    assert r.status_code == 200
    assert "stats" in r.json()
    assert r.json()["stats"]["running"] == 0

    # 9. Delete queue
    r = await auth_client.delete(f"/api/queues/{queue_id}")
    assert r.status_code == 204

    # 10. Confirm deleted
    r = await auth_client.get(f"/api/queues/{queue_id}")
    assert r.status_code == 404


async def test_queue_authorization(auth_client, auth_client_other):
    # 1. User A setup
    r = await auth_client.post("/api/projects", json={"name": "Project A"})
    project_id = r.json()["id"]
    r = await auth_client.post(
        f"/api/projects/{project_id}/queues",
        json={"name": "QueueA", "max_concurrency": 2}
    )
    queue_id = r.json()["id"]

    # 2. User B tries to view/modify User A's queue flat endpoints
    r = await auth_client_other.get(f"/api/queues/{queue_id}")
    assert r.status_code == 404

    r = await auth_client_other.patch(f"/api/queues/{queue_id}", json={"max_concurrency": 5})
    assert r.status_code == 404

    r = await auth_client_other.post(f"/api/queues/{queue_id}/pause")
    assert r.status_code == 404

    r = await auth_client_other.delete(f"/api/queues/{queue_id}")
    assert r.status_code == 404
