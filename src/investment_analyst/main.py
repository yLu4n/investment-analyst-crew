from investment_analyst.crew import InvestmentAnalystCrew


def run():

    inputs = {
        "portfolio": [
            {
                "ticker": "PETR4.SA",
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

    result = InvestmentAnalystCrew().crew().kickoff(inputs=inputs)

    print("\n\n=== Resultado da Análise ===\n")
    print(result)


if __name__ == "__main__":
    run()