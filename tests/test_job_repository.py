from datetime import timedelta

from investment_analyst.services.job_repository import (
    InMemoryAnalysisRepository,
    build_request_hash,
)


def test_request_cache_returns_completed_job_within_ttl():
    repository = InMemoryAnalysisRepository(cache_ttl=timedelta(hours=24))
    payload = {"portfolio": [{"ticker": "PETR4"}]}

    first_job = repository.create_job(payload, user_id="user-1")
    repository.mark_completed_with_result(
        first_job.id,
        result_payload={"ok": True},
        report_markdown="# Relatório",
    )

    second_job = repository.create_job(payload, user_id="user-1")

    assert second_job.id == first_job.id
    assert second_job.status == "completed"


def test_asset_cache_expires_by_ttl():
    repository = InMemoryAnalysisRepository(cache_ttl=timedelta(microseconds=1))
    repository.set_asset_cache("petr4", "fundamental", {"rating": "moderada"})

    assert repository.get_asset_cache("PETR4", "fundamental") is None


def test_update_job_persists_retry_and_progress_metadata():
    repository = InMemoryAnalysisRepository()
    job = repository.create_job({"portfolio": [{"ticker": "PETR4"}]}, user_id="user-1")

    updated = repository.update_job(
        job.id,
        status="running",
        current_step="retry_scheduled",
        progress_percentage=42,
        attempt_count=2,
        max_attempts=4,
        retry_backoff_seconds=0.5,
        error_message="temporary-failure",
    )

    assert updated.status == "running"
    assert updated.current_step == "retry_scheduled"
    assert updated.progress_percentage == 42
    assert updated.attempt_count == 2
    assert updated.max_attempts == 4
    assert updated.retry_backoff_seconds == 0.5
    assert updated.error_message == "temporary-failure"

    cleared = repository.update_job(
        job.id,
        retry_backoff_seconds=None,
        error_message=None,
    )

    assert cleared.retry_backoff_seconds is None
    assert cleared.error_message is None


def test_mark_completed_with_result_is_atomic_for_cache_and_status():
    repository = InMemoryAnalysisRepository()
    payload = {"portfolio": [{"ticker": "PETR4"}]}
    job = repository.create_job(payload, user_id="user-1")

    result = repository.mark_completed_with_result(
        job.id,
        result_payload={"ok": True},
        report_markdown="# Relatório",
    )
    cached_job = repository.get_cached_job_by_hash(
        build_request_hash(payload, user_id="user-1"),
    )

    assert result.job_id == job.id
    assert repository.get_result(job.id) == result
    assert cached_job is not None
    assert cached_job.id == job.id
    assert cached_job.status == "completed"
    assert cached_job.current_step == "completed"
    assert cached_job.progress_percentage == 100
    assert cached_job.completed_at is not None


def test_partial_result_is_not_returned_as_completed_cache():
    repository = InMemoryAnalysisRepository()
    payload = {"portfolio": [{"ticker": "PETR4"}]}
    job = repository.create_job(payload, user_id="user-1")
    repository.save_result(
        job.id,
        result_payload={"ok": True},
        report_markdown="# Relatório",
    )

    assert (
        repository.get_cached_job_by_hash(build_request_hash(payload, user_id="user-1"))
        is None
    )
