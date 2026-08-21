# backend/tests/test_projects.py
import pytest

async def test_project_crud(auth_client):
    # 1. Create project
    res = await auth_client.post("/api/projects", json={"name": "Project Alpha"})
    assert res.status_code == 200
    proj_id = res.json()["id"]
    assert res.json()["name"] == "Project Alpha"

    # 2. Get project
    res = await auth_client.get(f"/api/projects/{proj_id}")
    assert res.status_code == 200
    assert res.json()["name"] == "Project Alpha"

    # 3. List projects
    res = await auth_client.get("/api/projects")
    assert res.status_code == 200
    names = [p["name"] for p in res.json()]
    assert "Project Alpha" in names

    # 4. Patch project
    res = await auth_client.patch(f"/api/projects/{proj_id}", json={"name": "Project Omega"})
    assert res.status_code == 200
    assert res.json()["name"] == "Project Omega"

    # 5. Delete project
    res = await auth_client.delete(f"/api/projects/{proj_id}")
    assert res.status_code == 200
    assert res.json() == {"detail": "Project deleted successfully"}

    # 6. Retrieve deleted project (returns 404)
    res = await auth_client.get(f"/api/projects/{proj_id}")
    assert res.status_code == 404


async def test_project_authorization(auth_client, auth_client_other):
    # 1. User A creates project
    res = await auth_client.post("/api/projects", json={"name": "Org A Project"})
    assert res.status_code == 200
    proj_id = res.json()["id"]

    # 2. User B from Org B attempts to read User A's project -> should get 404
    res = await auth_client_other.get(f"/api/projects/{proj_id}")
    assert res.status_code == 404

    # 3. User B attempts to patch User A's project -> should get 404
    res = await auth_client_other.patch(f"/api/projects/{proj_id}", json={"name": "Hacked"})
    assert res.status_code == 404

    # 4. User B attempts to delete User A's project -> should get 404
    res = await auth_client_other.delete(f"/api/projects/{proj_id}")
    assert res.status_code == 404
