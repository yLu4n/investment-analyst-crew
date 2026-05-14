from __future__ import annotations

from datetime import UTC, datetime, timedelta
from time import sleep
from typing import Any, Callable

from investment_analyst.services.analysis_application_service import (
    AnalysisExecutionResult,
    run_investment_analysis,
)
from investment_analyst.services.job_dispatcher import (
    AnalysisDispatcher,
    LocalThreadDispatcher,
)
from investment_analyst.services.job_repository import (
    AnalysisJobRecord,
    AnalysisRepository,
    AnalysisResultRecord,
    build_request_hash,
    InMemoryAnalysisRepository,
)


AnalysisExecutor = Callable[[dict[str, Any], str], AnalysisExecutionResult]


def default_analysis_executor(
    payload: dict[str, Any],
    job_id: str,
) -> AnalysisExecutionResult:
    return run_investment_analysis(payload, job_id=job_id)


class AnalysisJobManager:
    def __init__(
        self,
        repository: AnalysisRepository | None = None,
        analysis_executor: AnalysisExecutor = default_analysis_executor,
        dispatcher: AnalysisDispatcher | None = None,
        *,
        max_attempts: int = 3,
        base_retry_delay_seconds: float = 0.1,
        max_retry_delay_seconds: float = 1.0,
        sleep_func: Callable[[float], None] = sleep,
    ) -> None:
        self.repository = repository or InMemoryAnalysisRepository()
        self.analysis_executor = analysis_executor
        self.dispatcher = dispatcher or LocalThreadDispatcher(worker=self._execute_job)
        self.max_attempts = max(1, max_attempts)
        self.base_retry_delay_seconds = max(0.0, base_retry_delay_seconds)
        self.max_retry_delay_seconds = max(
            self.base_retry_delay_seconds,
            max_retry_delay_seconds,
        )
        self.sleep_func = sleep_func

    def submit(self, payload: dict[str, Any], user_id: str | None = None) -> AnalysisJobRecord:
        job, _ = self.submit_with_cache_status(payload, user_id=user_id)
        return job

    def submit_with_cache_status(
        self,
        payload: dict[str, Any],
        user_id: str | None = None,
    ) -> tuple[AnalysisJobRecord, bool]:
        request_hash = build_request_hash(payload, user_id)
        cached_job = self.repository.get_cached_job_by_hash(request_hash)
        if cached_job:
            return cached_job, True

        active_job = self.repository.get_job_by_request_hash(request_hash)
        if active_job:
            return active_job, False

        job, created_new = self.repository.create_job_with_status(payload, user_id=user_id)
        if job.max_attempts != self.max_attempts:
            job = self.repository.update_job(job.id, max_attempts=self.max_attempts)
        if job.status == "completed":
            return job, True

        if created_new:
            self.dispatcher.enqueue(job.id, user_id=user_id)
        return job, False

    def get_status(self, job_id: str) -> AnalysisJobRecord | None:
        return self.repository.get_job(job_id)

    def get_result(self, job_id: str) -> tuple[AnalysisJobRecord, AnalysisResultRecord] | None:
        job = self.repository.get_job(job_id)
        if not job:
            return None
        result = self.repository.get_result(job_id)
        if not result:
            return None
        return job, result

    def _execute_job(self, job_id: str) -> None:
        started_at = datetime.now(UTC)
        job = self.repository.claim_pending_job(job_id, started_at=started_at)
        if not job:
            return

        for attempt_count in range(1, job.max_attempts + 1):
            try:
                job = self.repository.update_job(
                    job_id,
                    status="running",
                    current_step="preparing_analysis",
                    progress_percentage=10,
                    attempt_count=attempt_count,
                    retry_backoff_seconds=None,
                    next_retry_at=None,
                    error_message=None,
                    started_at=started_at,
                    completed_at=None,
                    failed_at=None,
                )
                self.repository.update_job(
                    job_id,
                    current_step="executing_analysis",
                    progress_percentage=45,
                )
                result = self.analysis_executor(job.input_payload, job_id)
                self.repository.update_job(
                    job_id,
                    current_step="persisting_result",
                    progress_percentage=90,
                )
                self.repository.mark_completed_with_result(
                    job_id,
                    result_payload=result.result_payload,
                    report_markdown=result.report_markdown,
                    pdf_path=result.pdf_path,
                    error_message=None,
                    retry_backoff_seconds=None,
                    next_retry_at=None,
                    completed_at=datetime.now(UTC),
                    failed_at=None,
                )
                return
            except Exception as exc:
                if attempt_count >= job.max_attempts:
                    self.repository.update_job(
                        job_id,
                        status="failed",
                        current_step="failed",
                        progress_percentage=100,
                        attempt_count=attempt_count,
                        error_message=str(exc),
                        retry_backoff_seconds=None,
                        next_retry_at=None,
                        failed_at=datetime.now(UTC),
                    )
                    return

                backoff_seconds = self._calculate_backoff_seconds(attempt_count)
                self.repository.update_job(
                    job_id,
                    status="running",
                    current_step="retry_scheduled",
                    progress_percentage=5,
                    attempt_count=attempt_count,
                    error_message=str(exc),
                    retry_backoff_seconds=backoff_seconds,
                    next_retry_at=datetime.now(UTC) + timedelta(seconds=backoff_seconds),
                )
                self.sleep_func(backoff_seconds)

    def _calculate_backoff_seconds(self, failed_attempt_count: int) -> float:
        backoff = self.base_retry_delay_seconds * (2 ** (failed_attempt_count - 1))
        return min(backoff, self.max_retry_delay_seconds)
