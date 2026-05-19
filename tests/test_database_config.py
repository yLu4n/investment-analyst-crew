from __future__ import annotations

from investment_analyst.persistence.database_config import (
    DEFAULT_TEST_DATABASE_URL,
    TEST_DATABASE_URL_ENV,
    get_test_database_url,
    require_test_database_url,
)


def test_test_database_url_reads_explicit_environment(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(TEST_DATABASE_URL_ENV, "sqlite:///tmp/test.db")

    assert get_test_database_url() == "sqlite:///tmp/test.db"


def test_test_database_url_defaults_to_in_memory_sqlite(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(TEST_DATABASE_URL_ENV, raising=False)

    assert get_test_database_url() == DEFAULT_TEST_DATABASE_URL


def test_require_test_database_url_returns_default_sqlite_url(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(TEST_DATABASE_URL_ENV, raising=False)

    assert require_test_database_url() == DEFAULT_TEST_DATABASE_URL
