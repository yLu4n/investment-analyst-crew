from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Callable

from investment_analyst.services.analysis_preparation_service import build_analysis_inputs
from investment_analyst.services.report_export_service import (
    export_markdown_report_to_pdf,
    read_report_or_result,
)


CrewRunner = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class AnalysisExecutionResult:
    result_payload: dict[str, Any]
    report_markdown: str
    pdf_path: str | None = None


def run_investment_analysis(
    raw_inputs: dict[str, Any],
    crew_runner: CrewRunner | None = None,
    export_pdf: bool = False,
    job_id: str | None = None,
) -> AnalysisExecutionResult:
    prepared_inputs = build_analysis_inputs(raw_inputs)
    report_path = _build_report_path(job_id)
    runner = crew_runner or _build_crewai_runner(report_path)
    crew_result = runner(prepared_inputs)
    report_markdown = read_report_or_result(
        report_path,
        crew_result,
    )
    pdf_path = (
        export_markdown_report_to_pdf(report_markdown, prepared_inputs["report_ticker"])
        if export_pdf
        else None
    )

    return AnalysisExecutionResult(
        result_payload={
            "prepared_inputs": prepared_inputs,
            "crew_result": str(crew_result),
        },
        report_markdown=report_markdown,
        pdf_path=pdf_path,
    )


def _build_crewai_runner(report_path: str) -> CrewRunner:
    def run(prepared_inputs: dict[str, Any]) -> Any:
        from investment_analyst.crew import InvestmentAnalystCrew

        return InvestmentAnalystCrew(report_output_path=report_path).crew().kickoff(
            inputs=prepared_inputs,
        )

    return run


def _build_report_path(job_id: str | None) -> str:
    if not job_id:
        return "outputs/investment_report.md"
    return os.path.join("outputs", "jobs", job_id, "investment_report.md")
