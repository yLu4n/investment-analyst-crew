from investment_analyst.crew import InvestmentAnalystCrew
from investment_analyst.services.analysis_preparation_service import build_analysis_inputs
from investment_analyst.services.report_export_service import (
    export_markdown_report_to_pdf,
    read_report_or_result,
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

    prepared_inputs = build_analysis_inputs(inputs)
    result = InvestmentAnalystCrew().crew().kickoff(inputs=prepared_inputs)
    markdown_report = read_report_or_result("outputs/investment_report.md", result)
    pdf_path = export_markdown_report_to_pdf(
        markdown_report,
        prepared_inputs["report_ticker"],
    )

    print("\n\n=== Resultado da Análise ===\n")
    print(result)
    print(f"\nPDF exportado em: {pdf_path}")


if __name__ == "__main__":
    run()
