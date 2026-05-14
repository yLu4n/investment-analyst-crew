from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Any, Literal, Protocol
from uuid import uuid4


JobStatus = Literal["pending", "running", "completed", "failed"]
_UNSET = object()


@dataclass(frozen=True)
class AnalysisResultRecord:
    job_id: str
    result_payload: dict[str, Any]
    report_markdown: str
    pdf_path: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class AnalysisJobRecord:
    id: str
    request_hash: str
    user_id: str | None
    input_payload: dict[str, Any]
    status: JobStatus = "pending"
    current_step: str = "queued"
    progress_percentage: int = 0
    attempt_count: int = 0
    max_attempts: int = 3
    retry_backoff_seconds: float | None = None
    next_retry_at: datetime | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class InMemoryAnalysisRepository:
    def __init__(self, cache_ttl: timedelta = timedelta(hours=24)) -> None:
        self.cache_ttl = cache_ttl
        self._jobs: dict[str, AnalysisJobRecord] = {}
        self._results: dict[str, AnalysisResultRecord] = {}
        self._request_cache: dict[str, str] = {}
        self._asset_cache: dict[str, tuple[datetime, dict[str, Any]]] = {}
        self._lock = RLock()

    def create_job(self, payload: dict[str, Any], user_id: str | None = None) -> AnalysisJobRecord:
        job, _ = self.create_job_with_status(payload, user_id=user_id)
        return job

    def create_job_with_status(
        self,
        payload: dict[str, Any],
        user_id: str | None = None,
    ) -> tuple[AnalysisJobRecord, bool]:
        request_hash = build_request_hash(payload, user_id)
        with self._lock:
            cached_job = self.get_cached_job_by_hash(request_hash)
            if cached_job:
                return cached_job, False

            existing_job = self.get_job_by_request_hash(request_hash)
            if existing_job:
                return existing_job, False

            job = AnalysisJobRecord(
                id=str(uuid4()),
                request_hash=request_hash,
                user_id=user_id,
                input_payload=payload,
            )
            self._jobs[job.id] = job
            self._request_cache[request_hash] = job.id
            return job, True

    def get_job(self, job_id: str) -> AnalysisJobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def get_result(self, job_id: str) -> AnalysisResultRecord | None:
        with self._lock:
            return self._results.get(job_id)

    def update_job(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        current_step: str | None = None,
        progress_percentage: int | None = None,
        attempt_count: int | None = None,
        max_attempts: int | None = None,
        retry_backoff_seconds: float | None | object = _UNSET,
        next_retry_at: datetime | None | object = _UNSET,
        error_message: str | None | object = _UNSET,
        started_at: datetime | None | object = _UNSET,
        completed_at: datetime | None | object = _UNSET,
        failed_at: datetime | None | object = _UNSET,
    ) -> AnalysisJobRecord:
        with self._lock:
            job = self._jobs[job_id]
            if status is not None:
                job.status = status
            if current_step is not None:
                job.current_step = current_step
            if progress_percentage is not None:
                job.progress_percentage = max(0, min(progress_percentage, 100))
            if attempt_count is not None:
                job.attempt_count = max(0, attempt_count)
            if max_attempts is not None:
                job.max_attempts = max(1, max_attempts)
            if retry_backoff_seconds is not _UNSET:
                job.retry_backoff_seconds = retry_backoff_seconds
            if next_retry_at is not _UNSET:
                job.next_retry_at = next_retry_at
            if error_message is not _UNSET:
                job.error_message = error_message
            if started_at is not _UNSET:
                job.started_at = started_at
            if completed_at is not _UNSET:
                job.completed_at = completed_at
            if failed_at is not _UNSET:
                job.failed_at = failed_at
            job.updated_at = datetime.now(UTC)
            return job

    def claim_pending_job(
        self,
        job_id: str,
        *,
        started_at: datetime | None = None,
    ) -> AnalysisJobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status != "pending":
                return None
            job.status = "running"
            job.started_at = started_at or datetime.now(UTC)
            job.updated_at = datetime.now(UTC)
            return job

    def save_result(
        self,
        job_id: str,
        *,
        result_payload: dict[str, Any],
        report_markdown: str,
        pdf_path: str | None = None,
    ) -> AnalysisResultRecord:
        with self._lock:
            result = AnalysisResultRecord(
                job_id=job_id,
                result_payload=result_payload,
                report_markdown=report_markdown,
                pdf_path=pdf_path,
            )
            self._results[job_id] = result
            return result

    def mark_completed_with_result(
        self,
        job_id: str,
        *,
        result_payload: dict[str, Any],
        report_markdown: str,
        pdf_path: str | None = None,
        error_message: str | None | object = _UNSET,
        retry_backoff_seconds: float | None | object = _UNSET,
        next_retry_at: datetime | None | object = _UNSET,
        completed_at: datetime | None = None,
        failed_at: datetime | None | object = _UNSET,
    ) -> AnalysisResultRecord:
        with self._lock:
            result = self.save_result(
                job_id,
                result_payload=result_payload,
                report_markdown=report_markdown,
                pdf_path=pdf_path,
            )
            self.update_job(
                job_id,
                status="completed",
                current_step="completed",
                progress_percentage=100,
                error_message=error_message,
                retry_backoff_seconds=retry_backoff_seconds,
                next_retry_at=next_retry_at,
                completed_at=completed_at or datetime.now(UTC),
                failed_at=failed_at,
            )
            return result

    def get_cached_job_by_hash(self, request_hash: str) -> AnalysisJobRecord | None:
        with self._lock:
            job_id = self._request_cache.get(request_hash)
            if not job_id:
                return None
            job = self._jobs.get(job_id)
            result = self._results.get(job_id)
            if not job or not result:
                return None
            if job.status != "completed":
                return None
            if datetime.now(UTC) - result.created_at > self.cache_ttl:
                self._request_cache.pop(request_hash, None)
                return None
            return job

    def get_job_by_request_hash(self, request_hash: str) -> AnalysisJobRecord | None:
        with self._lock:
            job_id = self._request_cache.get(request_hash)
            if not job_id:
                return None
            job = self._jobs.get(job_id)
            if not job or job.status not in {"pending", "running"}:
                return None
            return job

    def get_asset_cache(self, ticker: str, analysis_type: str) -> dict[str, Any] | None:
        key = _asset_cache_key(ticker, analysis_type)
        with self._lock:
            cached = self._asset_cache.get(key)
            if not cached:
                return None
            created_at, payload = cached
            if datetime.now(UTC) - created_at > self.cache_ttl:
                self._asset_cache.pop(key, None)
                return None
            return payload

    def set_asset_cache(
        self,
        ticker: str,
        analysis_type: str,
        payload: dict[str, Any],
    ) -> None:
        key = _asset_cache_key(ticker, analysis_type)
        with self._lock:
            self._asset_cache[key] = (datetime.now(UTC), payload)


class AnalysisRepository(Protocol):
    def create_job(
        self,
        payload: dict[str, Any],
        user_id: str | None = None,
    ) -> AnalysisJobRecord: ...

    def create_job_with_status(
        self,
        payload: dict[str, Any],
        user_id: str | None = None,
    ) -> tuple[AnalysisJobRecord, bool]: ...

    def get_job(self, job_id: str) -> AnalysisJobRecord | None: ...

    def get_result(self, job_id: str) -> AnalysisResultRecord | None: ...

    def update_job(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        current_step: str | None = None,
        progress_percentage: int | None = None,
        attempt_count: int | None = None,
        max_attempts: int | None = None,
        retry_backoff_seconds: float | None | object = _UNSET,
        next_retry_at: datetime | None | object = _UNSET,
        error_message: str | None | object = _UNSET,
        started_at: datetime | None | object = _UNSET,
        completed_at: datetime | None | object = _UNSET,
        failed_at: datetime | None | object = _UNSET,
    ) -> AnalysisJobRecord: ...

    def claim_pending_job(
        self,
        job_id: str,
        *,
        started_at: datetime | None = None,
    ) -> AnalysisJobRecord | None: ...

    def save_result(
        self,
        job_id: str,
        *,
        result_payload: dict[str, Any],
        report_markdown: str,
        pdf_path: str | None = None,
    ) -> AnalysisResultRecord: ...

    def mark_completed_with_result(
        self,
        job_id: str,
        *,
        result_payload: dict[str, Any],
        report_markdown: str,
        pdf_path: str | None = None,
        error_message: str | None | object = _UNSET,
        retry_backoff_seconds: float | None | object = _UNSET,
        next_retry_at: datetime | None | object = _UNSET,
        completed_at: datetime | None = None,
        failed_at: datetime | None | object = _UNSET,
    ) -> AnalysisResultRecord: ...

    def get_cached_job_by_hash(self, request_hash: str) -> AnalysisJobRecord | None: ...

    def get_job_by_request_hash(self, request_hash: str) -> AnalysisJobRecord | None: ...

    def get_asset_cache(self, ticker: str, analysis_type: str) -> dict[str, Any] | None: ...

    def set_asset_cache(
        self,
        ticker: str,
        analysis_type: str,
        payload: dict[str, Any],
    ) -> None: ...


def build_request_hash(payload: dict[str, Any], user_id: str | None = None) -> str:
    normalized = {
        "user_id": user_id or "anonymous",
        "payload": payload,
    }
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _asset_cache_key(ticker: str, analysis_type: str) -> str:
    return f"{ticker.strip().upper()}:{analysis_type.strip().lower()}"
