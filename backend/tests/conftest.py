# backend/tests/conftest.py
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.main import app
from app.database import Base, get_db
from app.config import settings

@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

TEST_DB_URL = settings.DATABASE_URL.rsplit("/", 1)[0] + "/scheduler_test"

engine = create_async_engine(TEST_DB_URL, future=True)
TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client(client):
    await client.post("/api/auth/register", json={
        "email": "test@example.com", "password": "password123", "org_name": "TestOrg"
    })
    resp = await client.post("/api/auth/login", data={"username": "test@example.com", "password": "password123"})
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest_asyncio.fixture
async def auth_client_other():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client2:
        await client2.post("/api/auth/register", json={
            "email": "other@example.com", "password": "password456", "org_name": "OtherOrg"
        })
        resp = await client2.post("/api/auth/login", data={"username": "other@example.com", "password": "password456"})
        token = resp.json()["access_token"]
        client2.headers["Authorization"] = f"Bearer {token}"
        yield client2