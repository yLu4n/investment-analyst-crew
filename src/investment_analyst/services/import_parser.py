from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from io import BytesIO, StringIO
from typing import Any, Iterable

import pandas as pd


MAX_IMPORT_SIZE_BYTES = 10 * 1024 * 1024
MAX_IMPORT_ROWS = 500
MAX_QUANTITY = 1_000_000_000
MAX_AVERAGE_PRICE = 1_000_000_000
REQUIRED_COLUMNS = frozenset({"ticker", "quantity", "average_price"})
ACCEPTED_MIME_TYPES = {
    "csv": {"", "text/csv", "application/csv", "application/vnd.ms-excel"},
    "pdf": {"", "application/pdf"},
}
REJECTED_CSV_SIGNATURES = (b"%PDF-", b"PK\x03\x04", b"\x89PNG", b"GIF8", b"\xff\xd8\xff")
TICKER_PATTERN = re.compile(r"^[A-Z0-9.]{1,20}$")
PUBLIC_MESSAGES = {
    "success": "Arquivo importado com sucesso.",
    "invalid_format": "Formato invalido. Envie apenas arquivo CSV ou PDF.",
    "empty_file": "O arquivo esta vazio. Envie um CSV ou PDF com dados da carteira.",
    "file_too_large": "O arquivo excede o tamanho maximo permitido de 10 MB.",
    "invalid_file": "Arquivo invalido ou corrompido. Verifique o arquivo e tente novamente.",
    "invalid_csv": "CSV invalido. Use as colunas ticker, quantity e average_price.",
    "invalid_pdf": "Nao foi possivel importar os ativos deste PDF. Use o template oficial.",
    "pdf_unavailable": "Importacao de PDF indisponivel no ambiente atual.",
    "invalid_numbers": "Quantidade deve ser maior que zero e preco medio nao pode ser negativo.",
    "too_many_assets": f"Arquivo excede o limite de {MAX_IMPORT_ROWS} ativos.",
    "generic_error": "Nao foi possivel importar o arquivo. Tente novamente ou preencha os ativos manualmente.",
}
HEADER_ALIASES = {
    "ticker": "ticker",
    "ativo": "ticker",
    "codigo": "ticker",
    "codigo_ativo": "ticker",
    "symbol": "ticker",
    "quantity": "quantity",
    "quantidade": "quantity",
    "qtd": "quantity",
    "average_price": "average_price",
    "preco_medio": "average_price",
    "preço_medio": "average_price",
    "preco médio": "average_price",
    "preço médio": "average_price",
    "asset_type": "asset_type",
    "tipo": "asset_type",
    "classe": "asset_type",
}


class ImportParseError(ValueError):
    def __init__(self, code_or_message: str, public_message: str | None = None) -> None:
        self.code = code_or_message if code_or_message in PUBLIC_MESSAGES else _public_code_for_message(code_or_message)
        self.public_message = public_message or PUBLIC_MESSAGES.get(code_or_message, code_or_message)
        super().__init__(self.public_message)


@dataclass(frozen=True)
class ImportedAsset:
    ticker: str
    quantity: float
    average_price: float
    asset_type: str = "stock"

    def to_payload(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "quantity": self.quantity,
            "average_price": self.average_price,
            "asset_type": self.asset_type,
        }

    def to_analysis_asset(self) -> dict[str, Any]:
        return self.to_payload()


@dataclass(frozen=True)
class ImportParseResult:
    assets: tuple[ImportedAsset, ...]
    source_format: str = "csv"
    public_message: str = PUBLIC_MESSAGES["success"]

    def to_payload(self) -> list[dict[str, Any]]:
        return [asset.to_payload() for asset in self.assets]

    def as_analysis_assets(self) -> list[dict[str, Any]]:
        return self.to_payload()


def parse_investment_import(
    *,
    filename: str,
    content: bytes,
    content_type: str = "",
    max_size_bytes: int = MAX_IMPORT_SIZE_BYTES,
    max_rows: int = MAX_IMPORT_ROWS,
) -> ImportParseResult:
    extension = _file_extension(filename)
    if extension not in ACCEPTED_MIME_TYPES:
        raise ImportParseError("invalid_format")

    normalized_content_type = content_type.split(";", maxsplit=1)[0].strip().lower()
    if normalized_content_type not in ACCEPTED_MIME_TYPES[extension]:
        raise ImportParseError("invalid_format")

    if not content:
        raise ImportParseError("empty_file")

    if len(content) > max_size_bytes:
        raise ImportParseError("file_too_large")

    if extension == "csv":
        return _parse_csv(content, max_rows=max_rows)

    return _parse_pdf(content, max_rows=max_rows)


def parse_portfolio_import(
    file_name: str,
    content: bytes,
    *,
    mime_type: str | None = None,
    max_size_bytes: int = MAX_IMPORT_SIZE_BYTES,
    max_assets: int = MAX_IMPORT_ROWS,
) -> ImportParseResult:
    return parse_investment_import(
        filename=file_name,
        content=content,
        content_type=mime_type or "",
        max_size_bytes=max_size_bytes,
        max_rows=max_assets,
    )


def _file_extension(filename: str) -> str | None:
    parts = filename.rsplit(".", maxsplit=1)
    if len(parts) != 2 or not parts[1].strip():
        return None
    return parts[1].strip().lower()


def _parse_csv(content: bytes, *, max_rows: int) -> ImportParseResult:
    if content.startswith(REJECTED_CSV_SIGNATURES) or b"\x00" in content[:256]:
        raise ImportParseError("invalid_file")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportParseError("invalid_file") from exc

    lines = text.splitlines()
    if not any(line.strip() for line in lines):
        raise ImportParseError("empty_file")

    first_line = next(line for line in lines if line.strip())
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    try:
        dataframe = pd.read_csv(
            StringIO(text),
            sep=delimiter,
            dtype=str,
            keep_default_na=False,
        )
    except Exception as exc:
        raise ImportParseError("invalid_csv") from exc

    return _assets_from_dataframe(dataframe, source_format="csv", max_rows=max_rows)


def _parse_pdf(content: bytes, *, max_rows: int) -> ImportParseResult:
    if not content.startswith(b"%PDF-"):
        raise ImportParseError("invalid_file")

    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportParseError("pdf_unavailable") from exc

    rows: list[list[str]] = []
    try:
        with pdfplumber.open(BytesIO(content)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    rows.extend([[_clean_cell(cell) for cell in row] for row in table if row])
                page_text = page.extract_text() or ""
                rows.extend(_rows_from_pdf_text(page_text))
    except Exception as exc:
        raise ImportParseError("invalid_pdf") from exc

    if not rows:
        raise ImportParseError("invalid_pdf")

    dataframe = _dataframe_from_rows(rows)
    return _assets_from_dataframe(dataframe, source_format="pdf", max_rows=max_rows)


def _rows_from_pdf_text(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        normalized = line.strip()
        if not normalized:
            continue
        if ";" in normalized:
            rows.append([part.strip() for part in normalized.split(";")])
            continue
        if "," in normalized:
            rows.append([part.strip() for part in normalized.split(",")])
            continue
        rows.append([part.strip() for part in re.split(r"\s{2,}|\t", normalized) if part.strip()])
    return rows


def _dataframe_from_rows(rows: list[list[str]]) -> pd.DataFrame:
    header_index = next(
        (
            index
            for index, row in enumerate(rows)
            if REQUIRED_COLUMNS.issubset({_canonical_header(cell) for cell in row})
        ),
        None,
    )
    if header_index is None:
        raise ImportParseError("invalid_pdf")

    headers = [_canonical_header(cell) for cell in rows[header_index]]
    data_rows = [
        row[: len(headers)]
        for row in rows[header_index + 1 :]
        if len(row) >= len(REQUIRED_COLUMNS) and any(cell.strip() for cell in row)
    ]
    return pd.DataFrame(data_rows, columns=headers)


def _assets_from_dataframe(dataframe: pd.DataFrame, *, source_format: str, max_rows: int) -> ImportParseResult:
    dataframe = dataframe.rename(columns={column: _canonical_header(str(column)) for column in dataframe.columns})
    missing_columns = REQUIRED_COLUMNS.difference(dataframe.columns)
    if missing_columns:
        raise ImportParseError("invalid_csv" if source_format == "csv" else "invalid_pdf")

    if dataframe.empty:
        raise ImportParseError("empty_file")

    if len(dataframe) > max_rows:
        raise ImportParseError("too_many_assets", f"Arquivo excede o limite de {max_rows} ativos.")

    assets = []
    for row_number, row in enumerate(dataframe.to_dict(orient="records"), start=2):
        try:
            assets.append(_asset_from_row(row))
        except ImportParseError as exc:
            public_message = (
                PUBLIC_MESSAGES["invalid_numbers"]
                if exc.code == "invalid_numbers"
                else exc.public_message
            )
            raise ImportParseError(exc.code, f"Linha {row_number}: {public_message}") from None
    if not assets:
        raise ImportParseError("empty_file")
    return ImportParseResult(assets=tuple(assets), source_format=source_format)


def _asset_from_row(row: dict[str, Any]) -> ImportedAsset:
    ticker = str(row.get("ticker", "")).strip().upper()
    if not TICKER_PATTERN.fullmatch(ticker):
        raise ImportParseError("Ticker invalido no arquivo importado.")

    quantity = _positive_number(row.get("quantity"), "Quantidade")
    average_price = _non_negative_number(row.get("average_price"), "Preco medio")
    asset_type = _safe_asset_type(row.get("asset_type") or "stock")

    return ImportedAsset(
        ticker=ticker[:-3] if ticker.endswith(".SA") else ticker,
        quantity=quantity,
        average_price=average_price,
        asset_type=asset_type,
    )


def _canonical_header(value: str) -> str:
    normalized = _safe_text(value, default="", max_length=64).strip().lower()
    normalized = re.sub(r"[\-/]+", "_", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return HEADER_ALIASES.get(normalized, normalized.replace(" ", "_"))


def _positive_number(value: Any, field_name: str) -> float:
    number = _decimal_number(value, field_name)
    if number <= 0 or number > MAX_QUANTITY:
        raise ImportParseError("invalid_numbers")
    return number


def _non_negative_number(value: Any, field_name: str) -> float:
    number = _decimal_number(value, field_name)
    if number < 0 or number > MAX_AVERAGE_PRICE:
        raise ImportParseError("invalid_numbers")
    return number


def _decimal_number(value: Any, field_name: str) -> float:
    text = str(value).strip()
    text = _normalize_decimal_separator(text)
    try:
        number = float(text)
    except (TypeError, ValueError) as exc:
        raise ImportParseError(f"{field_name} deve ser um numero.") from exc
    if not pd.notna(number):
        raise ImportParseError(f"{field_name} deve ser um numero.")
    return number


def _safe_text(value: Any, *, default: str, max_length: int) -> str:
    text = str(value or default).replace("\x00", "").strip()
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    if text[:1] in {"=", "+", "-", "@"}:
        raise ImportParseError("invalid_csv")
    if len(text) > max_length:
        raise ImportParseError("invalid_csv")
    return text


def _clean_cell(value: Any) -> str:
    return _safe_text(value, default="", max_length=128)


def assets_to_payload(assets: Iterable[ImportedAsset]) -> list[dict[str, Any]]:
    return [asset.to_payload() for asset in assets]


def _public_code_for_message(message: str) -> str:
    for code, public_message in PUBLIC_MESSAGES.items():
        if message == public_message:
            return code
    if "maior que zero" in message or "negativo" in message:
        return "invalid_numbers"
    if "PDF" in message:
        return "invalid_pdf"
    if "CSV" in message:
        return "invalid_csv"
    return "generic_error"


def _normalize_decimal_separator(value: str) -> str:
    value = value.replace("R$", "").replace("BRL", "").replace(" ", "").replace("\u00a0", "")
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            return value.replace(".", "").replace(",", ".")
        return value.replace(",", "")
    if "," in value:
        integer_part, _, decimal_part = value.partition(",")
        if len(decimal_part) == 3 and integer_part.lstrip("+-").isdigit():
            return value.replace(",", "")
        return value.replace(",", ".")
    if "." in value:
        integer_part, _, decimal_part = value.partition(".")
        if len(decimal_part) == 3 and integer_part.lstrip("+-").isdigit():
            return value.replace(".", "")
    return value


def _safe_asset_type(value: Any) -> str:
    text = _safe_text(value, default="stock", max_length=64).lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9_-]+", "_", text).strip("_")
    return text or "stock"


PortfolioImportError = ImportParseError
PortfolioImportResult = ImportParseResult
