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
from investment_analyst.services.analysis_application_service import AnalysisExecutionResult
from investment_analyst.services.job_manager import AnalysisJobManager
from investment_analyst.services.job_repository import InMemoryAnalysisRepository

JWT_SECRET = "test-secret"


def fake_analysis_executor(payload, job_id):
    return AnalysisExecutionResult(
        result_payload={"received": payload, "job_id": job_id},
        report_markdown="# Relatorio de teste",
    )


def build_client(*, require_auth=False, manager=None, **app_kwargs):
    manager = manager or AnalysisJobManager(
        repository=InMemoryAnalysisRepository(),
        analysis_executor=fake_analysis_executor,
    )
    return AsyncClient(
        transport=ASGITransport(
            app=create_app(
                manager,
                require_auth=require_auth,
                **app_kwargs,
            )
        ),
        base_url="http://testserver",
    )


async def wait_until_completed(client, job_id, headers=None):
    deadline = monotonic() + 2
    while monotonic() < deadline:
        response = await client.get(f"/api/v1/analysis/status/{job_id}", headers=headers)
        if response.json()["status"] == "completed":
            return response
        await anyio.sleep(0.01)
    raise AssertionError("Job nao concluiu dentro do prazo do teste.")


@pytest.mark.anyio
async def test_authenticated_result_endpoint_blocks_cross_user_access(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    manager = AnalysisJobManager(
        repository=InMemoryAnalysisRepository(),
        analysis_executor=fake_analysis_executor,
    )
    user_one_headers = {"Authorization": f"Bearer {make_token('user-1')}"}
    user_two_headers = {"Authorization": f"Bearer {make_token('user-2')}"}

    async with build_client(require_auth=True, manager=manager) as client:
        created = await client.post(
            "/api/v1/analysis",
            headers=user_one_headers,
            json={
                "assets": [{"ticker": "PETR4", "quantity": 100, "average_price": 32.5}],
            },
        )
        assert created.status_code == 202
        job_id = created.json()["job_id"]

        await wait_until_completed(client, job_id, headers=user_one_headers)
        own_result = await client.get(f"/api/v1/analysis/result/{job_id}", headers=user_one_headers)
        other_result = await client.get(f"/api/v1/analysis/result/{job_id}", headers=user_two_headers)

    assert own_result.status_code == 200
    assert other_result.status_code == 404


@pytest.mark.anyio
async def test_public_analysis_contract_rejects_client_controlled_user_id_field():
    async with build_client() as client:
        response = await client.post(
            "/api/v1/analysis",
            json={
                "assets": [{"ticker": "PETR4", "quantity": 100, "average_price": 32.5}],
                "user_id": "attacker-controlled",
            },
        )

    assert response.status_code == 422
    assert any(error["loc"][-1] == "user_id" for error in response.json()["detail"])


@pytest.mark.anyio
async def test_api_should_reject_excessive_asset_count():
    excessive_assets = [
        {"ticker": f"PETR{index}", "quantity": 1, "average_price": 1}
        for index in range(600)
    ]

    async with build_client() as client:
        response = await client.post(
            "/api/v1/analysis",
            json={
                "assets": excessive_assets,
                "monthly_contribution": 1000,
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Carteira excede o limite de 50 ativos."


@pytest.mark.anyio
async def test_api_should_reject_overlong_ticker_strings():
    async with build_client() as client:
        response = await client.post(
            "/api/v1/analysis",
            json={
                "assets": [
                    {
                        "ticker": "PETR4" * 1024,
                        "quantity": 1,
                        "average_price": 1,
                    }
                ],
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Ticker do ativo na posicao 0 excede 20 caracteres."


@pytest.mark.anyio
async def test_api_rejects_payload_above_configured_limit():
    large_note = "A" * 1024

    async with build_client(max_payload_bytes=256) as client:
        response = await client.post(
            "/api/v1/analysis",
            json={
                "assets": [{"ticker": "PETR4", "quantity": 1, "average_price": 1}],
                "financial_goals": {"notes": large_note},
            },
        )

    assert response.status_code == 413
    assert response.json()["detail"] == "Payload excede o limite de 256 bytes."


@pytest.mark.anyio
async def test_api_should_rate_limit_burst_requests(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    auth_headers = {"Authorization": f"Bearer {make_token('user-1')}"}

    async with build_client(
        require_auth=True,
        rate_limit_max_requests=3,
        rate_limit_window_seconds=60,
    ) as client:
        responses = []
        for index in range(4):
            responses.append(
                await client.post(
                    "/api/v1/analysis",
                    headers=auth_headers,
                    json={
                        "assets": [
                            {
                                "ticker": f"PETR{index}",
                                "quantity": 1,
                                "average_price": 1,
                            }
                        ],
                        "monthly_contribution": index,
                    },
                )
            )

    assert [response.status_code for response in responses] == [202, 202, 202, 429]
    assert responses[-1].json()["detail"] == "Limite de requisicoes excedido. Tente novamente em instantes."
    assert 1 <= int(responses[-1].headers["retry-after"]) <= 60


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
