import os
import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type

class NewsInput(BaseModel):
    query: str = Field(description="Nome da empresa ou ticker para buscar notícias")

class NewsScraperTool(BaseTool):
    name: str = "news_scraper"
    description: str = "Busca notícias recentes sobre um ativo ou empresa"
    args_schema: Type[BaseModel] = NewsInput

    def _run(self, query: str) -> list[dict]:
        api_key = os.getenv("NEWS_API_KEY")
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "language": "pt",
            "sortBy": "publishedAt",
            "pageSize": 10,
            "apiKey": api_key,
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        articles = response.json().get("articles", [])

        return [
            {
                "titulo": a["title"],
                "descricao": a["description"],
                "fonte": a["source"]["name"],
                "data": a["publishedAt"][:10],
                "url": a["url"],
            }
            for a in articles
            if a.get("title") and a.get("description")
        ]