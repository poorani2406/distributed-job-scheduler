# worker/app/main.py
import asyncio
import sys
import signal
import socket
import logging
import traceback

from app.config import settings
from app.api_client import ApiClient
from app.handlers import get_handler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("worker")


class WorkerRuntime:
    def __init__(self):
        self.api = ApiClient()
        self.worker_id: str | None = None
        self.semaphore = asyncio.Semaphore(settings.WORKER_CONCURRENCY)
        self.active_jobs: dict[str, asyncio.Task] = {}
        self.shutdown_event = asyncio.Event()

    async def register(self):
        hostname = socket.gethostname()
        data = await self.api.register(hostname, settings.WORKER_CONCURRENCY)
        self.worker_id = data["id"]
        log.info(f"Registered worker {self.worker_id} ({hostname}), concurrency={settings.WORKER_CONCURRENCY}")

    async def run_job(self, job: dict):
        job_id = job["id"]
        handler = get_handler(job["name"])
        error, logs, success = None, None, False
        try:
            result = await asyncio.wait_for(handler(job["payload"]), timeout=job["timeout_seconds"])
            logs = str(result)
            success = True
            log.info(f"Job {job_id} ({job['name']}) succeeded")
        except asyncio.TimeoutError:
            error = f"Job timed out after {job['timeout_seconds']}s"
            log.warning(f"Job {job_id} timed out")
        except Exception as e:
            error = f"{e}\n{traceback.format_exc()}"
            log.warning(f"Job {job_id} failed: {e}")
        finally:
            try:
                await self.api.complete(job_id, self.worker_id, success, error, logs)
            except Exception as e:
                log.error(f"Failed to report completion for job {job_id}: {e}")
            self.active_jobs.pop(job_id, None)
            self.semaphore.release()

    async def claim_loop(self):
        while not self.shutdown_event.is_set():
            free_slots = settings.WORKER_CONCURRENCY - len(self.active_jobs)
            if free_slots > 0:
                try:
                    jobs = await self.api.claim(self.worker_id, free_slots)
                except Exception as e:
                    log.error(f"Claim error: {e}")
                    jobs = []
                for job in jobs:
                    if self.shutdown_event.is_set():
                        break
                    await self.semaphore.acquire()
                    task = asyncio.create_task(self.run_job(job))
                    self.active_jobs[job["id"]] = task
            try:
                await asyncio.wait_for(self.shutdown_event.wait(), timeout=settings.WORKER_POLL_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                pass

    async def heartbeat_loop(self):
        while not self.shutdown_event.is_set():
            try:
                await self.api.heartbeat(self.worker_id, list(self.active_jobs.keys()))
            except Exception as e:
                log.error(f"Heartbeat error: {e}")
            try:
                await asyncio.wait_for(self.shutdown_event.wait(), timeout=settings.HEARTBEAT_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                pass

    async def shutdown(self):
        if self.shutdown_event.is_set() and not self.active_jobs:
            return
        log.info("Shutdown signal received. Draining active jobs...")
        self.shutdown_event.set()
        if self.active_jobs:
            log.info(f"Waiting for {len(self.active_jobs)} active job(s) to finish...")
            await asyncio.gather(*self.active_jobs.values(), return_exceptions=True)
        if self.worker_id:
            log.info(f"Deregistering worker {self.worker_id}...")
            await self.api.deregister(self.worker_id)
            self.worker_id = None
        await self.api.close()
        log.info("Shutdown complete.")

    async def run(self):
        await self.register()
        loop = asyncio.get_running_loop()
        if sys.platform != "win32":
            for sig in (signal.SIGTERM, signal.SIGINT):
                try:
                    loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
                except NotImplementedError:
                    pass
        try:
            await asyncio.gather(self.claim_loop(), self.heartbeat_loop())
        except asyncio.CancelledError:
            pass


async def main():
    runtime = WorkerRuntime()
    try:
        await runtime.run()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        await runtime.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
