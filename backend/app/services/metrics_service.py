# backend/app/services/metrics_service.py
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_org_metrics(db: AsyncSession, org_id) -> dict:
    status_counts = await db.execute(
        text("""
            SELECT j.status, COUNT(*)
            FROM jobs j
            JOIN queues q ON q.id = j.queue_id
            JOIN projects p ON p.id = q.project_id
            WHERE p.org_id = :org_id
            GROUP BY j.status
        """),
        {"org_id": org_id},
    )
    by_status = {row[0]: row[1] for row in status_counts.fetchall()}

    queue_stats = await db.execute(
        text("""
            SELECT q.id, q.name, q.max_concurrency, q.is_paused,
                   COUNT(*) FILTER (WHERE j.status = 'running') AS running,
                   COUNT(*) FILTER (WHERE j.status IN ('pending','scheduled','retrying')) AS queued,
                   COUNT(*) FILTER (WHERE j.status = 'dead') AS dead
            FROM queues q
            JOIN projects p ON p.id = q.project_id
            LEFT JOIN jobs j ON j.queue_id = q.id
            WHERE p.org_id = :org_id
            GROUP BY q.id, q.name, q.max_concurrency, q.is_paused
        """),
        {"org_id": org_id},
    )
    queues = [
        {
            "id": str(row[0]), "name": row[1], "max_concurrency": row[2],
            "is_paused": row[3], "running": row[4], "queued": row[5], "dead": row[6],
        }
        for row in queue_stats.fetchall()
    ]

    since = datetime.now(timezone.utc) - timedelta(hours=1)
    throughput = await db.execute(
        text("""
            SELECT COUNT(*)
            FROM jobs j
            JOIN queues q ON q.id = j.queue_id
            JOIN projects p ON p.id = q.project_id
            WHERE p.org_id = :org_id AND j.status = 'succeeded' AND j.completed_at >= :since
        """),
        {"org_id": org_id, "since": since},
    )
    succeeded_last_hour = throughput.scalar_one()

    worker_stats = await db.execute(
        text("SELECT status, COUNT(*) FROM workers GROUP BY status")
    )
    workers_by_status = {row[0]: row[1] for row in worker_stats.fetchall()}

    return {
        "jobs_by_status": by_status,
        "queues": queues,
        "succeeded_last_hour": succeeded_last_hour,
        "workers_by_status": workers_by_status,
    }