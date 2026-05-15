from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import math
import os
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_analyst.services.job_manager import AnalysisJobManager

PUBLIC_ERROR_MESSAGE = "Nao foi possivel concluir a analise. Tente novamente em instantes."
auth_scheme = HTTPBearer(auto_error=False)
DEFAULT_MAX_PAYLOAD_BYTES = 64 * 1024
DEFAULT_MAX_PORTFOLIO_ASSETS = 50
DEFAULT_MAX_TICKER_LENGTH = 20
DEFAULT_MAX_STRING_LENGTH = 512
DEFAULT_RATE_LIMIT_MAX_REQUESTS = 10
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60.0


@dataclass(frozen=True)
class ApiLimits:
    max_payload_bytes: int
    max_portfolio_assets: int
    max_ticker_length: int
    max_string_length: int


class SimpleRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max(1, max_requests)
        self.window_seconds = max(1.0, window_seconds)
        self._events: dict[str, deque[float]] = {}
        self._lock = RLock()

    def check(self, key: str) -> float | None:
        now = time.monotonic()
        window_start = now - self.window_seconds
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= window_start:
                events.popleft()
            if len(events) >= self.max_requests:
                retry_after = max(1, math.ceil(events[0] + self.window_seconds - now))
                return float(retry_after)
            events.append(now)
            return None


class MaxPayloadSizeMiddleware:
    def __init__(self, app: Any, *, max_payload_bytes: int) -> None:
        self.app = app
        self.max_payload_bytes = max(1, max_payload_bytes)

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if not _should_limit_request_body(scope):
            await self.app(scope, receive, send)
            return

        content_length = _content_length_from_scope(scope)
        if content_length is not None and content_length > self.max_payload_bytes:
            await self._send_limit_exceeded(scope, receive, send)
            return

        body_chunks: list[bytes] = []
        total_size = 0
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] != "http.request":
                await self.app(scope, receive, send)
                return
            chunk = message.get("body", b"")
            total_size += len(chunk)
            if total_size > self.max_payload_bytes:
                await self._send_limit_exceeded(scope, receive, send)
                return
            body_chunks.append(chunk)
            more_body = message.get("more_body", False)

        body = b"".join(body_chunks)
        replayed = False

        async def replay_receive() -> dict[str, Any]:
            nonlocal replayed
            if replayed:
                return {"type": "http.request", "body": b"", "more_body": False}
            replayed = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay_receive, send)

    async def _send_limit_exceeded(
        self,
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        response = JSONResponse(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            content={"detail": f"Payload excede o limite de {self.max_payload_bytes} bytes."},
        )
        await response(scope, receive, send)


class AuthenticatedUser(BaseModel):
    user_id: str
    email: str | None = None
    app_metadata: dict[str, Any] = Field(default_factory=dict)


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assets: list[dict[str, Any]] | None = None
    portfolio: list[dict[str, Any]] | None = None
    risk_profile: str | dict[str, Any] = "moderate"
    monthly_contribution: float = Field(default=0, ge=0)
    financial_goals: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_assets(self) -> "AnalysisRequest":
        selected_assets = self.assets or self.portfolio
        if not selected_assets:
            raise ValueError("Informe ao menos um ativo em assets ou portfolio.")
        return self

    def to_analysis_payload(self) -> dict[str, Any]:
        goals = {
            **self.financial_goals,
            "monthly_contribution": self.financial_goals.get(
                "monthly_contribution",
                self.monthly_contribution,
            ),
        }
        return {
            "portfolio": self.assets or self.portfolio or [],
            "risk_profile": self.risk_profile,
            "financial_goals": goals,
        }


class AnalysisCreatedResponse(BaseModel):
    job_id: str


class AnalysisStatusResponse(BaseModel):
    status: str
    current_step: str
    progress_percentage: int = Field(default=0, ge=0, le=100)
    attempt_count: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=1, ge=1)
    retry_backoff_seconds: float | None = Field(default=None, ge=0)
    next_retry_at: datetime | None = None
    error_message: str | None = None


class AnalysisResultResponse(BaseModel):
    job_id: str
    result_payload: dict[str, Any]
    report_markdown: str
    pdf_path: str | None = None


def create_app(
    job_manager: AnalysisJobManager | None = None,
    *,
    require_auth: bool | None = None,
    allowed_origins: list[str] | None = None,
    max_payload_bytes: int | None = None,
    max_portfolio_assets: int | None = None,
    max_ticker_length: int | None = None,
    max_string_length: int | None = None,
    rate_limit_max_requests: int | None = None,
    rate_limit_window_seconds: float | None = None,
) -> FastAPI:
    manager = job_manager or AnalysisJobManager()
    auth_required = require_auth if require_auth is not None else _env_flag("INVESTMENT_ANALYST_REQUIRE_AUTH", default=True)
    cors_origins = allowed_origins if allowed_origins is not None else _env_list(
        "INVESTMENT_ANALYST_ALLOWED_ORIGINS",
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
    )
    api_limits = ApiLimits(
        max_payload_bytes=max_payload_bytes
        if max_payload_bytes is not None
        else _env_int("INVESTMENT_ANALYST_MAX_PAYLOAD_BYTES", default=DEFAULT_MAX_PAYLOAD_BYTES, minimum=1),
        max_portfolio_assets=max_portfolio_assets
        if max_portfolio_assets is not None
        else _env_int(
            "INVESTMENT_ANALYST_MAX_PORTFOLIO_ASSETS",
            default=DEFAULT_MAX_PORTFOLIO_ASSETS,
            minimum=1,
        ),
        max_ticker_length=max_ticker_length
        if max_ticker_length is not None
        else _env_int(
            "INVESTMENT_ANALYST_MAX_TICKER_LENGTH",
            default=DEFAULT_MAX_TICKER_LENGTH,
            minimum=1,
        ),
        max_string_length=max_string_length
        if max_string_length is not None
        else _env_int(
            "INVESTMENT_ANALYST_MAX_STRING_LENGTH",
            default=DEFAULT_MAX_STRING_LENGTH,
            minimum=1,
        ),
    )
    rate_limiter = SimpleRateLimiter(
        max_requests=rate_limit_max_requests
        if rate_limit_max_requests is not None
        else _env_int(
            "INVESTMENT_ANALYST_RATE_LIMIT_MAX_REQUESTS",
            default=DEFAULT_RATE_LIMIT_MAX_REQUESTS,
            minimum=1,
        ),
        window_seconds=rate_limit_window_seconds
        if rate_limit_window_seconds is not None
        else _env_float(
            "INVESTMENT_ANALYST_RATE_LIMIT_WINDOW_SECONDS",
            default=DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
            minimum=1.0,
        ),
    )
    app = FastAPI(title="Investment Analyst API", version="0.1.0")
    app.add_middleware(
        MaxPayloadSizeMiddleware,
        max_payload_bytes=api_limits.max_payload_bytes,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.job_manager = manager
    app.state.require_auth = auth_required
    app.state.api_limits = api_limits
    app.state.rate_limiter = rate_limiter

    async def current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
    ) -> AuthenticatedUser | None:
        if not auth_required:
            return None
        return _authenticate_supabase_user(credentials)

    @app.post(
        "/api/v1/analysis",
        response_model=AnalysisCreatedResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_analysis(
        request: Request,
        analysis_request: AnalysisRequest,
        response: Response,
        user: AuthenticatedUser | None = Depends(current_user),
    ) -> AnalysisCreatedResponse:
        _enforce_analysis_request_limits(analysis_request, request.app.state.api_limits)
        _enforce_rate_limit(request, user)
        job, cache_hit = manager.submit_with_cache_status(
            analysis_request.to_analysis_payload(),
            user_id=user.user_id if user else None,
        )
        if cache_hit:
            response.status_code = status.HTTP_200_OK
        return AnalysisCreatedResponse(job_id=job.id)

    @app.get(
        "/api/v1/analysis/status/{job_id}",
        response_model=AnalysisStatusResponse,
    )
    async def get_analysis_status(
        job_id: str,
        user: AuthenticatedUser | None = Depends(current_user),
    ) -> AnalysisStatusResponse:
        job = manager.get_status(job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado.")
        _ensure_job_owner(job.user_id, user)
        return AnalysisStatusResponse(
            status=job.status,
            current_step=job.current_step,
            progress_percentage=job.progress_percentage,
            attempt_count=job.attempt_count,
            max_attempts=job.max_attempts,
            retry_backoff_seconds=job.retry_backoff_seconds,
            next_retry_at=job.next_retry_at,
            error_message=_public_error_message(job.error_message),
        )

    @app.get(
        "/api/v1/analysis/result/{job_id}",
        response_model=AnalysisResultResponse,
    )
    async def get_analysis_result(
        job_id: str,
        user: AuthenticatedUser | None = Depends(current_user),
    ) -> AnalysisResultResponse:
        job = manager.get_status(job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado.")
        _ensure_job_owner(job.user_id, user)
        if job.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Resultado ainda não disponível.",
            )

        job_and_result = manager.get_result(job_id)
        if not job_and_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resultado não encontrado.",
            )
        _, result = job_and_result
        return AnalysisResultResponse(
            job_id=job_id,
            result_payload=result.result_payload,
            report_markdown=result.report_markdown,
            pdf_path=result.pdf_path,
        )

    return app


def _env_flag(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _env_list(name: str, *, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if value is None:
        return default
    parsed = [item.strip() for item in value.split(",") if item.strip()]
    return parsed or default


def _env_int(name: str, *, default: int, minimum: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(minimum, parsed)


def _env_float(name: str, *, default: float, minimum: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return max(minimum, parsed)


def _authenticate_supabase_user(
    credentials: HTTPAuthorizationCredentials | None,
) -> AuthenticatedUser:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticacao obrigatoria.")

    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
    if not jwt_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Autenticacao indisponivel.")

    try:
        payload = _verify_hs256_jwt(credentials.credentials, jwt_secret)
    except (binascii.Error, json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido.") from None

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido.")

    app_metadata = payload.get("app_metadata")
    return AuthenticatedUser(
        user_id=subject,
        email=payload.get("email") if isinstance(payload.get("email"), str) else None,
        app_metadata=app_metadata if isinstance(app_metadata, dict) else {},
    )


def _verify_hs256_jwt(token: str, secret: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("invalid token")

    header = json.loads(_base64url_decode(parts[0]))
    if not isinstance(header, dict) or header.get("alg") != "HS256":
        raise ValueError("invalid algorithm")

    signing_input = f"{parts[0]}.{parts[1]}".encode("utf-8")
    expected_signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual_signature = _base64url_decode(parts[2])
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise ValueError("invalid signature")

    payload = json.loads(_base64url_decode(parts[1]))
    if not isinstance(payload, dict):
        raise ValueError("invalid payload")
    _validate_token_time_claims(payload)
    return payload


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("utf-8"))


def _validate_token_time_claims(payload: dict[str, Any]) -> None:
    now = int(time.time())
    expiration = payload.get("exp")
    not_before = payload.get("nbf")

    if expiration is not None and (not isinstance(expiration, int | float) or now >= expiration):
        raise ValueError("expired token")
    if not_before is not None and (not isinstance(not_before, int | float) or now < not_before):
        raise ValueError("token not active")


def _ensure_job_owner(job_user_id: str | None, user: AuthenticatedUser | None) -> None:
    if user and job_user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado.")


def _public_error_message(error_message: str | None) -> str | None:
    return PUBLIC_ERROR_MESSAGE if error_message else None


def _enforce_analysis_request_limits(
    request: AnalysisRequest,
    limits: ApiLimits,
) -> None:
    selected_assets = request.assets or request.portfolio or []
    if len(selected_assets) > limits.max_portfolio_assets:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Carteira excede o limite de {limits.max_portfolio_assets} ativos.",
        )

    for index, asset in enumerate(selected_assets):
        ticker = asset.get("ticker")
        if not isinstance(ticker, str) or not ticker.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Ticker do ativo na posicao {index} é obrigatório.",
            )
        if len(ticker.strip()) > limits.max_ticker_length:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Ticker do ativo na posicao {index} excede {limits.max_ticker_length} caracteres.",
            )
        _ensure_nested_strings_within_limit(
            asset,
            max_length=limits.max_string_length,
            path=f"assets[{index}]",
        )

    _ensure_nested_strings_within_limit(
        request.risk_profile,
        max_length=limits.max_string_length,
        path="risk_profile",
    )
    _ensure_nested_strings_within_limit(
        request.financial_goals,
        max_length=limits.max_string_length,
        path="financial_goals",
    )


def _ensure_nested_strings_within_limit(value: Any, *, max_length: int, path: str) -> None:
    if isinstance(value, str):
        if len(value) > max_length:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Campo {path} excede o limite de {max_length} caracteres.",
            )
        return
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if isinstance(key, str) and len(key) > max_length:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Chave {path} excede o limite de {max_length} caracteres.",
                )
            nested_path = f"{path}.{key}" if isinstance(key, str) else path
            _ensure_nested_strings_within_limit(
                nested_value,
                max_length=max_length,
                path=nested_path,
            )
        return
    if isinstance(value, list):
        for index, nested_value in enumerate(value):
            _ensure_nested_strings_within_limit(
                nested_value,
                max_length=max_length,
                path=f"{path}[{index}]",
            )


def _enforce_rate_limit(request: Request, user: AuthenticatedUser | None) -> None:
    key = _rate_limit_key(request, user)
    retry_after = request.app.state.rate_limiter.check(key)
    if retry_after is None:
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Limite de requisicoes excedido. Tente novamente em instantes.",
        headers={"Retry-After": str(int(retry_after))},
    )


def _rate_limit_key(request: Request, user: AuthenticatedUser | None) -> str:
    if user:
        return f"user:{user.user_id}"
    client_host = request.client.host if request.client else "unknown"
    return f"ip:{client_host}"


def _should_limit_request_body(scope: dict[str, Any]) -> bool:
    return (
        scope.get("type") == "http"
        and scope.get("method", "").upper() == "POST"
        and scope.get("path") == "/api/v1/analysis"
    )


def _content_length_from_scope(scope: dict[str, Any]) -> int | None:
    for key, value in scope.get("headers", []):
        if key == b"content-length":
            try:
                return int(value.decode("ascii"))
            except ValueError:
                return None
    return None


app = create_app()
