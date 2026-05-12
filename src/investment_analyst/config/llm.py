import os

from crewai import LLM
from dotenv import load_dotenv


load_dotenv()


def get_llm() -> LLM:
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()

    if provider == "openrouter":
        return LLM(
            model=os.getenv(
                "OPENROUTER_MODEL",
                "openrouter/inclusionai/ring-2.6-1t:free",
            ),
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
        )

    return LLM(
        model=os.getenv("GEMINI_MODEL", "gemini/gemini-2.5-flash"),
        api_key=os.getenv("GEMINI_API_KEY"),
    )