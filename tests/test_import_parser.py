from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from investment_analyst.services.import_parser import (
    MAX_IMPORT_ROWS,
    ImportParseError,
    parse_investment_import,
)


def test_parse_csv_template_normalizes_assets():
    content = Path("docs/templates/importacao-carteira-v1.csv").read_bytes()

    result = parse_investment_import(
        filename="importacao-carteira-v1.csv",
        content=content,
        content_type="text/csv",
    )

    assert result.to_payload()[0] == {
        "ticker": "PETR4",
        "quantity": 100.0,
        "average_price": 32.5,
        "asset_type": "stock",
    }
    assert len(result.assets) == 3


def test_parse_csv_accepts_portuguese_aliases_and_decimal_comma():
    result = parse_investment_import(
        filename="carteira.csv",
        content="ativo;quantidade;preco_medio;tipo\npetr4.sa;10,5;32,50;stock\n".encode(),
        content_type="text/csv",
    )

    assert result.to_payload() == [
        {
            "ticker": "PETR4",
            "quantity": 10.5,
            "average_price": 32.5,
            "asset_type": "stock",
        }
    ]


def test_parse_csv_rejects_disguised_or_invalid_payloads():
    cases = [
        ("%PDF-1.7", "wallet.csv", "text/csv"),
        ("ticker,quantity\nPETR4,10\n", "wallet.csv", "text/csv"),
        ("ticker,quantity,average_price\nPETR4,0,10\n", "wallet.csv", "text/csv"),
        ("ticker,quantity,average_price\n<script>,1,10\n", "wallet.csv", "text/csv"),
    ]

    for content, filename, content_type in cases:
        with pytest.raises(ImportParseError) as exc_info:
            parse_investment_import(
                filename=filename,
                content=content.encode(),
                content_type=content_type,
            )
        assert "<script" not in exc_info.value.public_message.lower()


def test_parse_rejects_invalid_extension_mime_size_and_empty_file():
    with pytest.raises(ImportParseError, match="Formato invalido"):
        parse_investment_import(filename="wallet.txt", content=b"ticker,quantity", content_type="text/plain")

    with pytest.raises(ImportParseError, match="Formato invalido"):
        parse_investment_import(filename="wallet.csv", content=b"ticker,quantity", content_type="application/json")

    with pytest.raises(ImportParseError, match="vazio"):
        parse_investment_import(filename="wallet.csv", content=b"", content_type="text/csv")

    with pytest.raises(ImportParseError, match="10 MB"):
        parse_investment_import(filename="wallet.csv", content=b"a" * (10 * 1024 * 1024 + 1), content_type="text/csv")


def test_parse_csv_rejects_excessive_rows():
    rows = ["ticker,quantity,average_price"]
    rows.extend(f"PETR{index},1,10" for index in range(MAX_IMPORT_ROWS + 1))

    with pytest.raises(ImportParseError, match=str(MAX_IMPORT_ROWS)):
        parse_investment_import(
            filename="wallet.csv",
            content=("\n".join(rows) + "\n").encode(),
            content_type="text/csv",
        )


def test_parse_pdf_uses_pdfplumber_tables(monkeypatch):
    class FakePage:
        def extract_tables(self):
            return [
                [
                    ["ticker", "quantity", "average_price", "asset_type"],
                    ["PETR4", "10", "32.50", "stock"],
                ]
            ]

        def extract_text(self):
            return ""

    class FakePdf:
        pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setitem(sys.modules, "pdfplumber", SimpleNamespace(open=lambda _: FakePdf()))

    result = parse_investment_import(
        filename="carteira.pdf",
        content=b"%PDF-1.7 fake fixture",
        content_type="application/pdf",
    )

    assert result.to_payload() == [
        {
            "ticker": "PETR4",
            "quantity": 10.0,
            "average_price": 32.5,
            "asset_type": "stock",
        }
    ]


def test_parse_pdf_rejects_invalid_signature():
    with pytest.raises(ImportParseError, match="corrompido"):
        parse_investment_import(
            filename="carteira.pdf",
            content=b"not a pdf",
            content_type="application/pdf",
        )
