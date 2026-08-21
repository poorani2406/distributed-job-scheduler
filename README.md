# Distributed Job Scheduler

A production-style distributed job scheduling platform featuring a FastAPI backend, PostgreSQL-backed atomic job claiming, asynchronous worker daemon pools, and an interactive React operator dashboard.

## 📁 System Documentation
Detailed engineering specifications are available in the `docs/` directory:
- 🛠️ **[Architecture Design](docs/architecture.md)**: Details components interactions, loops lifecycles, and high-level layout.
- 🗄️ **[Database & Schema Specs](docs/database.md)**: Includes the ER diagram, schema details, unique constraints, and cascade delete settings.
- 🔌 **[API Endpoints Reference](docs/api.md)**: Fully documents REST routes, request payloads, and query structures.
- 📐 **[Design Decisions & Trade-offs](docs/design-decisions.md)**: Explains transaction choices, locks (`FOR UPDATE SKIP LOCKED`), and worker heartbeats.
- 🧪 **[Testing Framework](docs/testing.md)**: Explains the automated Pytest structure and test executions.

---

## 🛠️ Technology Stack
- **API Engine**: FastAPI, Pydantic V2, OAuth2 / JWT Auth
- **ORM & Migrations**: SQLAlchemy 2.0 (Async), Alembic
- **Database**: PostgreSQL 16
- **Worker Daemon**: Standalone Async Python Service (executes tasks concurrently via asyncio)
- **Frontend Dashboard**: React + Vite, Tailwind-free Vanilla CSS custom system
- **Test Automation**: Pytest, Pytest-Asyncio, HTTPX AsyncClient

---

## 🚀 Quickstart Guide

### 1. Build and Start the Services
Copy environment parameters and boot the containers:
```bash
cp .env.example .env
docker compose up --build -d
```
This starts:
- **PostgreSQL (`db`)**: Port `5432`
- **FastAPI API Server (`backend`)**: Port `8000`
- **React Frontend (`frontend`)**: Port `5173`
- **Worker Pool (`worker`)**: Polling backend

### 2. Apply Schema Migrations
Run Alembic upgrades head to prepare the tables and performance indexes:
```bash
docker compose exec backend alembic upgrade head
```

### 3. Verification URLs
- **Web Operator UI**: [http://localhost:5173/](http://localhost:5173/)
- **Swagger Interactive API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **OpenAPI Schema Specs JSON**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## 🧪 Running Automated Tests

Run the full suite of 16 tests inside the isolated test database environment:
```bash
# 1. Create the test database inside the postgres container (if not already done)
docker compose exec db createdb -U scheduler scheduler_test || true

# 2. Run the pytest runner
docker compose run backend pytest -v
```
All tests verify concurrency claim safety, queue limits, auth security, and state-transitions.