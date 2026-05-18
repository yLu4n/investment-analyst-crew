from __future__ import annotations

import pytest

from investment_analyst.persistence.database_config import (
    TEST_DATABASE_URL_ENV,
    get_test_database_url,
    require_test_database_url,
)


def test_test_database_url_reads_explicit_environment(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(TEST_DATABASE_URL_ENV, "postgresql+psycopg://user:pass@localhost:5432/test_db")

    assert get_test_database_url() == "postgresql+psycopg://user:pass@localhost:5432/test_db"


def test_require_test_database_url_explains_missing_configuration(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(TEST_DATABASE_URL_ENV, raising=False)

    with pytest.raises(RuntimeError, match=TEST_DATABASE_URL_ENV):
        require_test_database_url()
