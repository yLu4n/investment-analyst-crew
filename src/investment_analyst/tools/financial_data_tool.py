import os
import requests

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type

class FinancialDataInput(BaseModel):
    ticker: str = Field(description="Ticker do ativo (ex: PETR4, VALE3, MXRF11)")

class FinancialDataTool(BaseTool):
    name: str = "financial_data_fetcher"
    description: str = "Coleta dados financeiros de ativos da B3 via Brapi"
    args_schema: Type[BaseModel] = FinancialDataInput

    def _run(self, ticker: str) -> dict:
        
        ticker = ticker.replace(".SA", "").upper()
        
        token = os.getenv("BRAPI_TOKEN")
        url = f"https://brapi.dev/api/quote/{ticker}"
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        params = {
            "fundamental": "true",
            "dividends": "true",
            "range": "1mo",
            "interval": "1d",
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()

            result = data["results"][0]
            return {
                "ticker": ticker,
                "nome": result.get("longName"),
                "preco_atual": result.get("regularMarketPrice"),
                "variacao_dia": result.get("regularMarketChangePercent"),
                "pl": result.get("priceEarnings"),
                "dy": result.get("dividendsYield"),
                "market_cap": result.get("marketCap"),
                "volume": result.get("regularMarketVolume"),
                "52s_max": result.get("fiftyTwoWeekHigh"),
                "52s_min": result.get("fiftyTwoWeekLow"),
            }
        except requests.exceptions.Timeout:
            return {"error": "A requisição para a API Brapi excedeu o tempo limite."}
        except requests.exceptions.HTTPError as e:
            return {"error": f"Erro HTTP ao acessar a API Brapi: {str(e)}"}
        except Exception as e:
            return {"error": f"Ocorreu um erro ao processar a requisição: {str(e)}"}
