from investment_analyst.crew import InvestmentAnalystCrew
from investment_analyst.services.analysis_application_service import (
    AnalysisExecutionResult,
    run_investment_analysis,
)


def run():

    inputs = {
        "portfolio": [
            {
                "ticker": "PETR4.SA",
                "quantity": 100,
                "average_price": 32.50,
                "asset_type": "stock",
            },
            {
                "ticker": "VALE3.SA",
                "quantity": 100,
                "average_price": 32.50,
                "asset_type": "stock",
            },
        ],
        "risk_profile": {
            "profile": "moderado",
            "investment_experience": "intermediário",
            "liquidity_need": "média",
        },
        "financial_goals": {
            "goal_type": "monthly_income",
            "target_monthly_income": 5000,
            "time_horizon_months": 120,
            "monthly_contribution": 1500,
        },
    }

    result = run_investment_analysis(
        inputs,
        crew_runner=_run_crew,
        export_pdf=True,
    )

    print("\n\n=== Resultado da Análise ===\n")
    print(result.result_payload["crew_result"])
    print(f"\nPDF exportado em: {result.pdf_path}")


def _run_crew(prepared_inputs: dict) -> AnalysisExecutionResult | object:
    return InvestmentAnalystCrew().crew().kickoff(inputs=prepared_inputs)


if __name__ == "__main__":
    run()
