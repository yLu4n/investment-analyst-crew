from time import monotonic

import anyio
import pytest
from httpx import ASGITransport, AsyncClient

from investment_analyst.api import create_app
from investment_analyst.services.analysis_application_service import AnalysisExecutionResult
from investment_analyst.services.job_manager import AnalysisJobManager
from investment_analyst.services.job_repository import InMemoryAnalysisRepository


def fake_analysis_executor(payload, job_id):
    return AnalysisExecutionResult(
        result_payload={"received": payload, "job_id": job_id},
        report_markdown="# Relatório de teste",
    )


def build_client(manager=None):
    manager = manager or AnalysisJobManager(
        repository=InMemoryAnalysisRepository(),
        analysis_executor=fake_analysis_executor,
    )
    return AsyncClient(
        transport=ASGITransport(app=create_app(manager)),
        base_url="http://testserver",
    )


async def wait_until_completed(client, job_id):
    deadline = monotonic() + 2
    while monotonic() < deadline:
        response = await client.get(f"/api/v1/analysis/status/{job_id}")
        if response.json()["status"] == "completed":
            return response
        await anyio.sleep(0.01)
    raise AssertionError("Job não concluiu dentro do prazo do teste.")


async def wait_until_terminal_state(client, job_id):
    deadline = monotonic() + 2
    while monotonic() < deadline:
        response = await client.get(f"/api/v1/analysis/status/{job_id}")
        if response.json()["status"] in {"completed", "failed"}:
            return response
        await anyio.sleep(0.01)
    raise AssertionError("Job não atingiu estado terminal dentro do prazo do teste.")


@pytest.mark.anyio
async def test_create_status_and_result_flow():
    async with build_client() as client:
        created = await client.post(
            "/api/v1/analysis",
            json={
                "assets": [{"ticker": "PETR4", "quantity": 100, "average_price": 32.5}],
                "risk_profile": "moderate",
                "monthly_contribution": 1000,
            },
        )

        assert created.status_code == 202
        job_id = created.json()["job_id"]

        status_response = await wait_until_completed(client, job_id)
        assert status_response.json() == {
            "status": "completed",
            "current_step": "completed",
            "progress_percentage": 100,
            "attempt_count": 1,
            "max_attempts": 3,
            "retry_backoff_seconds": None,
            "next_retry_at": None,
            "error_message": None,
        }

        result_response = await client.get(f"/api/v1/analysis/result/{job_id}")
        assert result_response.status_code == 200
        assert result_response.json()["report_markdown"] == "# Relatório de teste"


@pytest.mark.anyio
async def test_identical_request_returns_cached_job_id():
    payload = {
        "user_id": "user-1",
        "assets": [{"ticker": "PETR4", "quantity": 100, "average_price": 32.5}],
    }
    async with build_client() as client:
        first = await client.post("/api/v1/analysis", json=payload)
        await wait_until_completed(client, first.json()["job_id"])
        second = await client.post("/api/v1/analysis", json=payload)

        assert first.json()["job_id"] == second.json()["job_id"]
        assert second.status_code == 200


@pytest.mark.anyio
async def test_result_before_completion_returns_conflict():
    manager = AnalysisJobManager(
        repository=InMemoryAnalysisRepository(),
        analysis_executor=fake_analysis_executor,
    )
    job = manager.repository.create_job({"portfolio": [{"ticker": "PETR4"}]})
    async with AsyncClient(
        transport=ASGITransport(app=create_app(manager)),
        base_url="http://testserver",
    ) as client:
        response = await client.get(f"/api/v1/analysis/result/{job.id}")

    assert response.status_code == 409


@pytest.mark.anyio
async def test_status_exposes_retry_metadata_after_terminal_failure():
    def failing_executor(payload, job_id):
        raise RuntimeError("temporary-downstream-error")

    manager = AnalysisJobManager(
        repository=InMemoryAnalysisRepository(),
        analysis_executor=failing_executor,
        max_attempts=2,
        base_retry_delay_seconds=0,
        max_retry_delay_seconds=0,
    )

    async with build_client(manager=manager) as client:
        created = await client.post(
            "/api/v1/analysis",
            json={
                "assets": [{"ticker": "PETR4", "quantity": 100, "average_price": 32.5}],
                "risk_profile": "moderate",
            },
        )
        status_response = await wait_until_terminal_state(client, created.json()["job_id"])

    assert status_response.status_code == 200
    assert status_response.json() == {
        "status": "failed",
        "current_step": "failed",
        "progress_percentage": 100,
        "attempt_count": 2,
        "max_attempts": 2,
        "retry_backoff_seconds": None,
        "next_retry_at": None,
        "error_message": "temporary-downstream-error",
    }
