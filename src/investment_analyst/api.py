from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_analyst.services.job_manager import AnalysisJobManager


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    assets: list[dict[str, Any]] | None = None
    portfolio: list[dict[str, Any]] | None = None
    risk_profile: str | dict[str, Any] = "moderate"
    monthly_contribution: float = Field(default=0, ge=0)
    financial_goals: dict[str, Any] = Field(default_factory=dict)
    user_id: str | None = None

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


def create_app(job_manager: AnalysisJobManager | None = None) -> FastAPI:
    manager = job_manager or AnalysisJobManager()
    app = FastAPI(title="Investment Analyst API", version="0.1.0")
    app.state.job_manager = manager

    @app.post(
        "/api/v1/analysis",
        response_model=AnalysisCreatedResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_analysis(
        request: AnalysisRequest,
        response: Response,
    ) -> AnalysisCreatedResponse:
        job, cache_hit = manager.submit_with_cache_status(
            request.to_analysis_payload(),
            user_id=request.user_id,
        )
        if cache_hit:
            response.status_code = status.HTTP_200_OK
        return AnalysisCreatedResponse(job_id=job.id)

    @app.get(
        "/api/v1/analysis/status/{job_id}",
        response_model=AnalysisStatusResponse,
    )
    async def get_analysis_status(job_id: str) -> AnalysisStatusResponse:
        job = manager.get_status(job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado.")
        return AnalysisStatusResponse(
            status=job.status,
            current_step=job.current_step,
            progress_percentage=job.progress_percentage,
            attempt_count=job.attempt_count,
            max_attempts=job.max_attempts,
            retry_backoff_seconds=job.retry_backoff_seconds,
            next_retry_at=job.next_retry_at,
            error_message=job.error_message,
        )

    @app.get(
        "/api/v1/analysis/result/{job_id}",
        response_model=AnalysisResultResponse,
    )
    async def get_analysis_result(job_id: str) -> AnalysisResultResponse:
        job = manager.get_status(job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado.")
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


app = create_app()
