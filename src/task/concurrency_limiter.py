import asyncio
from src.utils.config import config

class TaskSlotLimiter:
    def __init__(self, max_slots: int | None = None):
        self._sem = asyncio.Semaphore(max_slots or config.max_parallel_tasks)

    async def acquire(self):
        await self._sem.acquire()

    def release(self):
        self._sem.release()

    @property
    def available(self) -> int:
        return self._sem._value

task_slot_limiter = TaskSlotLimiter()
