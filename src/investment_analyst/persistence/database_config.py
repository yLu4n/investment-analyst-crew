from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


TEST_DATABASE_URL_ENV = "INVESTMENT_ANALYST_TEST_DATABASE_URL"
DATABASE_URL_ENV = "DATABASE_URL"


def load_database_env() -> None:
    root = Path.cwd()
    load_dotenv(root / ".env", override=False)
    load_dotenv(root / ".env.test", override=True)


def get_database_url() -> str | None:
    load_database_env()
    return _blank_to_none(os.getenv(DATABASE_URL_ENV))


def get_test_database_url() -> str | None:
    load_database_env()
    return _blank_to_none(os.getenv(TEST_DATABASE_URL_ENV))


def require_test_database_url() -> str:
    database_url = get_test_database_url()
    if not database_url:
        raise RuntimeError(
            f"Configure {TEST_DATABASE_URL_ENV} em .env.test para rodar testes de banco."
        )
    return database_url


def _blank_to_none(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()


__all__ = [
    "DATABASE_URL_ENV",
    "TEST_DATABASE_URL_ENV",
    "get_database_url",
    "get_test_database_url",
    "load_database_env",
    "require_test_database_url",
]

