import base64
import hashlib
import hmac
import json
import time
from time import monotonic

import anyio
import pytest
from httpx import ASGITransport, AsyncClient

from investment_analyst.api import create_app
import investment_analyst.persistence
from investment_analyst.services.analysis_application_service import AnalysisExecutionResult
from investment_analyst.services.job_manager import AnalysisJobManager
from investment_analyst.services.job_repository import InMemoryAnalysisRepository

JWT_SECRET = "test-secret"


def test_persistence_package_import_is_lazy():
    assert "Base" in investment_analyst.persistence.__all__


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
        transport=ASGITransport(app=create_app(manager, require_auth=False)),
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
async def test_cors_allows_local_next_frontend():
    async with build_client() as client:
        response = await client.options(
            "/api/v1/analysis",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


@pytest.mark.anyio
async def test_cors_allows_configured_frontend_origin():
    async with AsyncClient(
        transport=ASGITransport(
            app=create_app(
                require_auth=False,
                allowed_origins=["https://app.example.com"],
            )
        ),
        base_url="http://testserver",
    ) as client:
        response = await client.options(
            "/api/v1/analysis",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://app.example.com"


@pytest.mark.anyio
async def test_identical_request_returns_cached_job_id():
    payload = {
        "assets": [{"ticker": "PETR4", "quantity": 100, "average_price": 32.5}],
    }
    async with build_client() as client:
        first = await client.post("/api/v1/analysis", json=payload)
        await wait_until_completed(client, first.json()["job_id"])
        second = await client.post("/api/v1/analysis", json=payload)

        assert first.json()["job_id"] == second.json()["job_id"]
        assert second.status_code == 200


@pytest.mark.anyio
async def test_authenticated_api_uses_token_subject_and_blocks_cross_user_access(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    manager = AnalysisJobManager(
        repository=InMemoryAnalysisRepository(),
        analysis_executor=fake_analysis_executor,
    )
    user_one_headers = {"Authorization": f"Bearer {make_token('user-1')}"}
    user_two_headers = {"Authorization": f"Bearer {make_token('user-2')}"}

    async with AsyncClient(
        transport=ASGITransport(app=create_app(manager, require_auth=True)),
        base_url="http://testserver",
    ) as client:
        created = await client.post(
            "/api/v1/analysis",
            headers=user_one_headers,
            json={
                "assets": [{"ticker": "PETR4", "quantity": 100, "average_price": 32.5}],
                "risk_profile": "moderate",
            },
        )
        assert created.status_code == 202
        job_id = created.json()["job_id"]

        assert manager.get_status(job_id).user_id == "user-1"
        assert (await client.get(f"/api/v1/analysis/status/{job_id}", headers=user_one_headers)).status_code == 200
        assert (await client.get(f"/api/v1/analysis/status/{job_id}", headers=user_two_headers)).status_code == 404


@pytest.mark.anyio
async def test_authenticated_api_rejects_missing_or_invalid_token(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    async with AsyncClient(
        transport=ASGITransport(app=create_app(require_auth=True)),
        base_url="http://testserver",
    ) as client:
        missing = await client.post("/api/v1/analysis", json={"assets": [{"ticker": "PETR4"}]})
        invalid = await client.post(
            "/api/v1/analysis",
            headers={"Authorization": "Bearer invalid"},
            json={"assets": [{"ticker": "PETR4"}]},
        )

    assert missing.status_code == 401
    assert invalid.status_code == 401


@pytest.mark.anyio
async def test_api_rejects_portfolio_above_server_side_limit():
    async with AsyncClient(
        transport=ASGITransport(
            app=create_app(
                require_auth=False,
                max_portfolio_assets=2,
            )
        ),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/analysis",
            json={
                "assets": [
                    {"ticker": "PETR4"},
                    {"ticker": "VALE3"},
                    {"ticker": "ITUB4"},
                ]
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Carteira excede o limite de 2 ativos."


@pytest.mark.anyio
async def test_api_rejects_excessive_ticker_and_string_lengths():
    async with AsyncClient(
        transport=ASGITransport(
            app=create_app(
                require_auth=False,
                max_ticker_length=5,
                max_string_length=12,
            )
        ),
        base_url="http://testserver",
    ) as client:
        ticker_response = await client.post(
            "/api/v1/analysis",
            json={"assets": [{"ticker": "PETR4LONG"}]},
        )
        string_response = await client.post(
            "/api/v1/analysis",
            json={
                "assets": [{"ticker": "PETR4"}],
                "risk_profile": {"summary": "x" * 20},
            },
        )

    assert ticker_response.status_code == 422
    assert ticker_response.json()["detail"] == "Ticker do ativo na posicao 0 excede 5 caracteres."
    assert string_response.status_code == 422
    assert string_response.json()["detail"] == "Campo risk_profile.summary excede o limite de 12 caracteres."


@pytest.mark.anyio
async def test_api_rejects_payload_above_server_side_limit():
    async with AsyncClient(
        transport=ASGITransport(
            app=create_app(
                require_auth=False,
                max_payload_bytes=256,
            )
        ),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/analysis",
            json={
                "assets": [{"ticker": "PETR4"}],
                "risk_profile": "x" * 500,
            },
        )

    assert response.status_code == 413
    assert response.json()["detail"] == "Payload excede o limite de 256 bytes."


@pytest.mark.anyio
async def test_authenticated_rate_limit_is_isolated_per_user(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    manager = AnalysisJobManager(
        repository=InMemoryAnalysisRepository(),
        analysis_executor=fake_analysis_executor,
    )
    user_one_headers = {"Authorization": f"Bearer {make_token('user-1')}"}
    user_two_headers = {"Authorization": f"Bearer {make_token('user-2')}"}

    async with AsyncClient(
        transport=ASGITransport(
            app=create_app(
                manager,
                require_auth=True,
                rate_limit_max_requests=1,
                rate_limit_window_seconds=60,
            )
        ),
        base_url="http://testserver",
    ) as client:
        first_user_one = await client.post(
            "/api/v1/analysis",
            headers=user_one_headers,
            json={"assets": [{"ticker": "PETR4"}]},
        )
        first_user_two = await client.post(
            "/api/v1/analysis",
            headers=user_two_headers,
            json={"assets": [{"ticker": "VALE3"}]},
        )
        second_user_one = await client.post(
            "/api/v1/analysis",
            headers=user_one_headers,
            json={"assets": [{"ticker": "ITUB4"}]},
        )

    assert first_user_one.status_code == 202
    assert first_user_two.status_code == 202
    assert second_user_one.status_code == 429
    assert int(second_user_one.headers["retry-after"]) >= 1


@pytest.mark.anyio
async def test_result_before_completion_returns_conflict():
    manager = AnalysisJobManager(
        repository=InMemoryAnalysisRepository(),
        analysis_executor=fake_analysis_executor,
    )
    job = manager.repository.create_job({"portfolio": [{"ticker": "PETR4"}]})
    async with AsyncClient(
        transport=ASGITransport(app=create_app(manager, require_auth=False)),
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
        "error_message": "Nao foi possivel concluir a analise. Tente novamente em instantes.",
    }


def make_token(subject: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": subject,
        "email": f"{subject}@example.com",
        "app_metadata": {"plan": "pro"},
        "exp": int(time.time()) + 300,
    }
    signing_input = f"{base64url_json(header)}.{base64url_json(payload)}"
    signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    return f"{signing_input}.{base64url(signature)}"


def base64url_json(payload: dict) -> str:
    return base64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))


def base64url(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")
