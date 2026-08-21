# worker/app/handlers.py
import asyncio
import random

"""
Job handlers registry. Map job `name` -> async callable(payload: dict) -> dict.
Unregistered names fall back to `default_handler`.
"""


async def default_handler(payload: dict) -> dict:
    duration = payload.get("duration_seconds", 1)
    await asyncio.sleep(duration)
    if payload.get("fail"):
        raise RuntimeError(payload.get("fail_message", "Simulated failure"))
    return {"echo": payload}


async def flaky_handler(payload: dict) -> dict:
    await asyncio.sleep(0.5)
    if random.random() < payload.get("fail_rate", 0.5):
        raise RuntimeError("Flaky handler failed")
    return {"ok": True}


HANDLERS = {
    "default": default_handler,
    "flaky": flaky_handler,
}


def get_handler(name: str):
    return HANDLERS.get(name, default_handler)