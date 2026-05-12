
import os
import requests

ticker = "BBDC4"

token = os.getenv("BRAPI_TOKEN")
headers ={
    "Authorization": f"Bearer {token}",
}
params = {
    "fundamental": "true",
    "history": "true",
}
url = f"https://brapi.dev/api/quote/{ticker}/?fundamental={params['fundamental']}&history={params['history']}&token={token}"
        
try:
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    result = data["results"][0]
    print({"ticker": ticker,
        "nome": result.get("longName"),
        "preco_atual": result.get("regularMarketPrice"),
        "variacao_dia": result.get("regularMarketChangePercent"),
        "pl": result.get("priceEarnings"),
        "dy": result.get("dividendsYield"),
        "market_cap": result.get("marketCap"),
        "volume": result.get("regularMarketVolume"),
        "52s_max": result.get("fiftyTwoWeekHigh"),
        "52s_min": result.get("fiftyTwoWeekLow"),}
    )
except requests.exceptions.Timeout:
    print({"error": "A requisição para a API Brapi excedeu o tempo limite."})
except requests.exceptions.HTTPError as e:
    print({"error": f"Erro HTTP ao acessar a API Brapi: {str(e)}"})
except Exception as e:
    print({"error": f"Ocorreu um erro ao processar a requisição: {str(e)}"})
