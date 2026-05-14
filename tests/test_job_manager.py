from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import sleep

from investment_analyst.services.analysis_application_service import AnalysisExecutionResult
from investment_analyst.services.job_dispatcher import LocalThreadDispatcher
from investment_analyst.services.job_manager import AnalysisJobManager
from investment_analyst.services.job_repository import InMemoryAnalysisRepository


class RecordingDispatcher:
    def __init__(self) -> None:
        self.enqueued = []

    def enqueue(self, job_id, user_id=None):
        self.enqueued.append((job_id, user_id))


class InlineExecutor:
    def submit(self, fn, /, *args, **kwargs):
        fn(*args, **kwargs)


def test_submit_uses_dispatcher_port_instead_of_running_directly():
    dispatcher = RecordingDispatcher()
    manager = AnalysisJobManager(
        repository=InMemoryAnalysisRepository(),
        analysis_executor=lambda payload, job_id: AnalysisExecutionResult({}, ""),
        dispatcher=dispatcher,
    )

    job = manager.submit({"portfolio": [{"ticker": "PETR4"}]}, user_id="user-1")

    assert dispatcher.enqueued == [(job.id, "user-1")]
    assert manager.get_status(job.id).status == "pending"


def test_local_thread_dispatcher_executes_injected_worker():
    executed = []
    dispatcher = LocalThreadDispatcher(
        worker=executed.append,
        executor=InlineExecutor(),
    )

    dispatcher.enqueue("job-1", user_id="user-1")

    assert executed == ["job-1"]


def test_identical_active_request_reuses_queued_job_without_reenqueuing():
    dispatcher = RecordingDispatcher()
    manager = AnalysisJobManager(
        repository=InMemoryAnalysisRepository(),
        analysis_executor=lambda payload, job_id: AnalysisExecutionResult({}, ""),
        dispatcher=dispatcher,
    )
    payload = {"portfolio": [{"ticker": "PETR4"}]}

    first_job, first_cache_hit = manager.submit_with_cache_status(payload, user_id="user-1")
    second_job, second_cache_hit = manager.submit_with_cache_status(payload, user_id="user-1")

    assert first_job.id == second_job.id
    assert first_cache_hit is False
    assert second_cache_hit is False
    assert dispatcher.enqueued == [(first_job.id, "user-1")]


def test_concurrent_identical_requests_enqueue_only_once():
    dispatcher = RecordingDispatcher()
    manager = AnalysisJobManager(
        repository=InMemoryAnalysisRepository(),
        analysis_executor=lambda payload, job_id: AnalysisExecutionResult({}, ""),
        dispatcher=dispatcher,
    )
    payload = {"portfolio": [{"ticker": "PETR4"}]}

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(manager.submit_with_cache_status, payload, "user-1")
            for _ in range(2)
        ]

    results = [future.result() for future in futures]
    job_ids = {job.id for job, _ in results}

    assert len(job_ids) == 1
    assert [cache_hit for _, cache_hit in results] == [False, False]
    assert dispatcher.enqueued == [(results[0][0].id, "user-1")]


def test_execute_job_retries_with_exponential_backoff_and_completes():
    attempts = {"count": 0}
    sleep_calls = []

    def flaky_executor(payload, job_id):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError(f"temporary-{attempts['count']}")
        return AnalysisExecutionResult({"ok": True}, "# Relatório")

    repository = InMemoryAnalysisRepository()
    manager = AnalysisJobManager(
        repository=repository,
        analysis_executor=flaky_executor,
        dispatcher=RecordingDispatcher(),
        max_attempts=3,
        base_retry_delay_seconds=0.25,
        max_retry_delay_seconds=1.0,
        sleep_func=sleep_calls.append,
    )
    job = manager.submit({"portfolio": [{"ticker": "PETR4"}]}, user_id="user-1")

    manager._execute_job(job.id)

    status = manager.get_status(job.id)
    result = manager.get_result(job.id)

    assert sleep_calls == [0.25, 0.5]
    assert status.status == "completed"
    assert status.current_step == "completed"
    assert status.progress_percentage == 100
    assert status.attempt_count == 3
    assert status.max_attempts == 3
    assert status.retry_backoff_seconds is None
    assert status.next_retry_at is None
    assert status.error_message is None
    assert status.started_at is not None
    assert status.completed_at is not None
    assert status.failed_at is None
    assert result is not None
    assert result[1].result_payload == {"ok": True}


def test_execute_job_marks_terminal_failure_after_last_retry():
    sleep_calls = []

    def failing_executor(payload, job_id):
        raise RuntimeError("permanent-failure")

    repository = InMemoryAnalysisRepository()
    manager = AnalysisJobManager(
        repository=repository,
        analysis_executor=failing_executor,
        dispatcher=RecordingDispatcher(),
        max_attempts=3,
        base_retry_delay_seconds=0.2,
        max_retry_delay_seconds=0.4,
        sleep_func=sleep_calls.append,
    )
    job = manager.submit({"portfolio": [{"ticker": "PETR4"}]}, user_id="user-1")

    manager._execute_job(job.id)

    status = manager.get_status(job.id)

    assert sleep_calls == [0.2, 0.4]
    assert status.status == "failed"
    assert status.current_step == "failed"
    assert status.progress_percentage == 100
    assert status.attempt_count == 3
    assert status.max_attempts == 3
    assert status.retry_backoff_seconds is None
    assert status.next_retry_at is None
    assert status.error_message == "permanent-failure"
    assert status.started_at is not None
    assert status.completed_at is None
    assert status.failed_at is not None
    assert manager.get_result(job.id) is None


def test_execute_job_ignores_terminal_job_replay():
    calls = {"count": 0}

    def counting_executor(payload, job_id):
        calls["count"] += 1
        return AnalysisExecutionResult({"count": calls["count"]}, "# Relatório")

    repository = InMemoryAnalysisRepository()
    manager = AnalysisJobManager(
        repository=repository,
        analysis_executor=counting_executor,
        dispatcher=RecordingDispatcher(),
    )
    job = manager.submit({"portfolio": [{"ticker": "PETR4"}]}, user_id="user-1")

    manager._execute_job(job.id)
    manager._execute_job(job.id)

    result = manager.get_result(job.id)

    assert calls["count"] == 1
    assert result is not None
    assert result[1].result_payload == {"count": 1}


def test_execute_job_claims_pending_job_once_under_concurrent_replay():
    started = Event()
    calls = {"count": 0}

    def counting_executor(payload, job_id):
        started.set()
        sleep(0.05)
        calls["count"] += 1
        return AnalysisExecutionResult({"count": calls["count"]}, "# Relatório")

    repository = InMemoryAnalysisRepository()
    manager = AnalysisJobManager(
        repository=repository,
        analysis_executor=counting_executor,
        dispatcher=RecordingDispatcher(),
    )
    job = manager.submit({"portfolio": [{"ticker": "PETR4"}]}, user_id="user-1")

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(manager._execute_job, job.id)
        assert started.wait(timeout=2)
        second = executor.submit(manager._execute_job, job.id)
        futures = [first, second]

    for future in futures:
        future.result()
    result = manager.get_result(job.id)

    assert calls["count"] == 1
    assert result is not None
    assert result[1].result_payload == {"count": 1}
