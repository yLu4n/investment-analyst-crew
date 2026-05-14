from __future__ import annotations

from collections import defaultdict
from concurrent.futures import Executor, ThreadPoolExecutor
from threading import Lock
from typing import Callable, Protocol


JobWorker = Callable[[str], None]


class AnalysisDispatcher(Protocol):
    def enqueue(
        self,
        job_id: str,
        user_id: str | None = None,
    ) -> None: ...


class LocalThreadDispatcher:
    def __init__(
        self,
        worker: JobWorker,
        executor: Executor | None = None,
    ) -> None:
        self.worker = worker
        self.executor = executor or ThreadPoolExecutor(max_workers=2)
        self._user_locks: defaultdict[str, Lock] = defaultdict(Lock)

    def enqueue(
        self,
        job_id: str,
        user_id: str | None = None,
    ) -> None:
        self.executor.submit(self._run_serialized, job_id, user_id)

    def _run_serialized(
        self,
        job_id: str,
        user_id: str | None,
    ) -> None:
        lock_key = user_id or "anonymous"
        with self._user_locks[lock_key]:
            self.worker(job_id)
