import os
import re
import unicodedata
from datetime import datetime
from xml.sax.saxutils import escape

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, HRFlowable, PageBreak, Preformatted
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

PDF_SAFE_REPLACEMENTS = str.maketrans({
    "\u00a0": " ",
    "\u200b": "",
    "\u200c": "",
    "\u200d": "",
    "\ufe0f": "",
    "\ufeff": "",
    "“": '"',
    "”": '"',
    "„": '"',
    "’": "'",
    "‘": "'",
    "‚": "'",
    "–": "-",
    "—": "-",
    "−": "-",
    "…": "...",
    "→": "->",
    "←": "<-",
    "↔": "<->",
    "⇒": "=>",
    "⇐": "<=",
    "⚠": "[!]",
    "✅": "[OK]",
    "❌": "[X]",
    "🟢": "[BAIXO]",
    "🟡": "[MEDIO]",
    "🔴": "[ALTO]",
    "📊": "[GRAFICO]",
    "📈": "[ALTA]",
    "📉": "[BAIXA]",
    "📖": "[NOTA]",
    "🏦": "[RENDA FIXA]",
    "🏠": "[FIIS]",
    "🌍": "[GLOBAL]",
    "💡": "[IDEIA]",
    "🚨": "[ALERTA]",
    "✓": "[OK]",
    "✔": "[OK]",
    "✗": "[X]",
    "✘": "[X]",
    "•": "*",
    "·": "-",
    "│": "|",
    "┃": "|",
    "┆": "|",
    "┇": "|",
    "┊": "|",
    "┋": "|",
    "┌": "+",
    "┐": "+",
    "└": "+",
    "┘": "+",
    "├": "+",
    "┤": "+",
    "┬": "+",
    "┴": "+",
    "┼": "+",
    "═": "=",
    "║": "|",
    "╔": "+",
    "╗": "+",
    "╚": "+",
    "╝": "+",
    "╠": "+",
    "╣": "+",
    "╦": "+",
    "╩": "+",
    "╬": "+",
    "─": "-",
    "━": "-",
    "█": "#",
    "▓": "#",
    "▒": "=",
    "░": "-",
})

MAX_CODE_BLOCK_LINES_PER_TABLE = 65


class PDFInput(BaseModel):
    ticker: str = Field(description="Ticker do ativo analisado")
    conteudo: str = Field(description="Conteúdo completo do relatório em texto")

class PDFGeneratorTool(BaseTool):
    name: str = "pdf_generator"
    description: str = "Gera um relatório profissional em PDF com a análise completa do ativo"
    args_schema: Type[BaseModel] = PDFInput

    def _run(self, ticker: str, conteudo: str) -> str:
        os.makedirs("outputs", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"outputs/relatorio_{ticker}_{timestamp}.pdf"
        _build_pdf(filename, ticker, conteudo)
        return f"PDF gerado com sucesso: {filename}"


def _get_styles():
    styles = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle(
            "Titulo", parent=styles["Title"],
            fontSize=22, textColor=colors.HexColor("#1a1a2e"),
            leading=26, spaceAfter=6, alignment=TA_CENTER,
        ),
        "subtitulo": ParagraphStyle(
            "Subtitulo", parent=styles["Normal"],
            fontSize=11, textColor=colors.HexColor("#4a4a6a"),
            leading=14, spaceAfter=4, alignment=TA_CENTER,
        ),
        "h1": ParagraphStyle(
            "H1", parent=styles["Heading1"],
            fontSize=14, textColor=colors.HexColor("#1a1a2e"),
            leading=18, spaceBefore=16, spaceAfter=6, alignment=TA_LEFT,
        ),
        "h2": ParagraphStyle(
            "H2", parent=styles["Heading2"],
            fontSize=12, textColor=colors.HexColor("#2e4057"),
            leading=15, spaceBefore=10, spaceAfter=4,
        ),
        "corpo": ParagraphStyle(
            "Corpo", parent=styles["Normal"],
            fontSize=10, textColor=colors.HexColor("#2d2d2d"),
            leading=15, spaceAfter=6, alignment=TA_JUSTIFY,
        ),
        "bullet": ParagraphStyle(
            "Bullet", parent=styles["Normal"],
            fontSize=10, textColor=colors.HexColor("#2d2d2d"),
            leading=15, spaceAfter=4,
            leftIndent=16, firstLineIndent=-10,
        ),
        "table_header": ParagraphStyle(
            "TableHeader", parent=styles["Normal"],
            fontName="Helvetica-Bold", fontSize=9, leading=11,
            textColor=colors.white, alignment=TA_LEFT,
        ),
        "table_cell": ParagraphStyle(
            "TableCell", parent=styles["Normal"],
            fontSize=8.5, leading=10.5,
            textColor=colors.HexColor("#1f2933"), alignment=TA_LEFT,
        ),
        "code": ParagraphStyle(
            "Code", parent=styles["Code"],
            fontName="Courier", fontSize=7.5, leading=9,
            textColor=colors.HexColor("#1f2933"),
        ),
        "aviso": ParagraphStyle(
            "Aviso", parent=styles["Normal"],
            fontSize=8.5, leading=10.5,
            textColor=colors.HexColor("#7a5c00"),
        ),
        "rodape": ParagraphStyle(
            "Rodape", parent=styles["Normal"],
            fontSize=8, textColor=colors.HexColor("#888888"),
            alignment=TA_CENTER,
        ),
    }


def _sanitize_text(texto: str, preserve_spacing: bool = False) -> str:
    if texto is None:
        return ""

    sanitized = texto.replace("\r\n", "\n").replace("\r", "\n").translate(PDF_SAFE_REPLACEMENTS)
    if preserve_spacing:
        sanitized = sanitized.replace("\t", "    ")
    else:
        sanitized = sanitized.replace("\t", " ")

    cleaned_chars = []
    for char in sanitized:
        if char == "\n":
            cleaned_chars.append(char)
            continue
        try:
            char.encode("latin-1")
            cleaned_chars.append(char)
            continue
        except UnicodeEncodeError:
            pass

        fallback = []
        for normalized_char in unicodedata.normalize("NFKD", char):
            if unicodedata.combining(normalized_char):
                continue
            try:
                normalized_char.encode("latin-1")
                fallback.append(normalized_char)
            except UnicodeEncodeError:
                continue

        if fallback:
            cleaned_chars.extend(fallback)
        elif unicodedata.category(char).startswith("Z"):
            cleaned_chars.append(" ")
        else:
            cleaned_chars.append(" " if preserve_spacing else "")

    return "".join(cleaned_chars)


def _parse_conteudo(conteudo: str, styles: dict) -> list:
    """Converte texto markdown-like em elementos ReportLab."""
    story = []
    conteudo = _strip_outer_markdown_fence(conteudo)
    linhas = conteudo.split("\n")
    index = 0

    while index < len(linhas):
        linha_original = linhas[index]
        linha = linha_original.strip()
        if not linha:
            story.append(Spacer(1, 0.2*cm))
            index += 1
            continue

        if linha.startswith("```"):
            block_lines = []
            index += 1
            while index < len(linhas) and not linhas[index].strip().startswith("```"):
                block_lines.append(linhas[index])
                index += 1
            if index < len(linhas):
                index += 1
            story.extend(_build_code_block(block_lines, styles))
            story.append(Spacer(1, 0.3*cm))
            continue

        if _is_indented_code_start(linhas, index):
            block_lines = []
            while index < len(linhas):
                current_line = linhas[index]
                if _is_indented_code_line(current_line):
                    block_lines.append(_strip_code_indentation(current_line))
                    index += 1
                    continue
                if not current_line.strip() and block_lines:
                    block_lines.append("")
                    index += 1
                    continue
                break
            story.extend(_build_code_block(block_lines, styles))
            story.append(Spacer(1, 0.3*cm))
            continue

        if _is_table_start(linhas, index):
            table_lines = []
            while index < len(linhas) and _is_table_line(linhas[index]):
                table_lines.append(linhas[index].strip())
                index += 1
            story.append(_build_markdown_table(table_lines, styles))
            story.append(Spacer(1, 0.3*cm))
            continue

        if linha in {"---", "***", "___"}:
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
            index += 1
            continue

        if linha.startswith("# ") or (linha.isupper() and len(linha) < 60):
            texto = linha.lstrip("# ").strip()
            story.append(Paragraph(_convert_markdown(texto), styles["h1"]))
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
            index += 1
            continue

        if linha.startswith("## "):
            texto = linha.lstrip("# ").strip()
            story.append(Paragraph(_convert_markdown(texto), styles["h2"]))
            index += 1
            continue

        if linha.startswith("### "):
            texto = linha.lstrip("# ").strip()
            story.append(Paragraph(_convert_markdown(texto), styles["h2"]))
            index += 1
            continue

        if linha.startswith("* ") or linha.startswith("- ") or linha.startswith("• "):
            texto = linha.lstrip("*-• ").strip()
            texto = _convert_markdown(texto)
            story.append(Paragraph(f"- {texto}", styles["bullet"]))
            index += 1
            continue

        if linha.startswith("**") and linha.endswith("**"):
            texto = _sanitize_text(linha.strip("*"))
            story.append(Paragraph(f"<b>{escape(texto)}</b>", styles["corpo"]))
            index += 1
            continue

        texto = _convert_markdown(linha)
        story.append(Paragraph(texto, styles["corpo"]))
        index += 1

    return story


def _strip_outer_markdown_fence(conteudo: str) -> str:
    lines = conteudo.splitlines()
    first_content_index = next(
        (index for index, line in enumerate(lines) if line.strip()),
        None,
    )
    if first_content_index is None:
        return conteudo

    last_content_index = next(
        (index for index in range(len(lines) - 1, -1, -1) if lines[index].strip()),
        first_content_index,
    )

    first_line = lines[first_content_index].strip().lower()
    last_line = lines[last_content_index].strip()
    fence_match = re.fullmatch(r"```(?:markdown|md)", first_line)
    if not fence_match or last_line != "```":
        return conteudo

    unwrapped_lines = (
        lines[:first_content_index]
        + lines[first_content_index + 1:last_content_index]
        + lines[last_content_index + 1:]
    )
    return "\n".join(unwrapped_lines)


def _convert_markdown(texto: str) -> str:
    """Converte **negrito** e *itálico* para tags ReportLab."""
    texto = escape(_sanitize_text(texto))
    texto = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', texto)
    texto = re.sub(r'\*(.+?)\*', r'<i>\1</i>', texto)
    texto = re.sub(r'`([^`]+)`', r'<font face="Courier">\1</font>', texto)
    return texto


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|")


def _is_table_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    return _is_table_line(lines[index]) and _is_table_separator(lines[index + 1])


def _is_table_separator(line: str) -> bool:
    if not _is_table_line(line):
        return False
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)


def _split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_indented_code_line(line: str) -> bool:
    return line.startswith("    ") or line.startswith("\t")


def _is_indented_code_start(lines: list[str], index: int) -> bool:
    if not _is_indented_code_line(lines[index]):
        return False
    return index == 0 or not lines[index - 1].strip()


def _strip_code_indentation(line: str) -> str:
    if line.startswith("\t"):
        return line[1:]
    if line.startswith("    "):
        return line[4:]
    return line


def _build_code_block(block_lines: list[str], styles: dict) -> list[Table]:
    safe_lines = []
    for line in block_lines:
        safe_lines.extend(_wrap_code_line(_sanitize_text(line, preserve_spacing=True)))
    if not safe_lines:
        safe_lines = [" "]

    tables = []
    for chunk_start in range(0, len(safe_lines), MAX_CODE_BLOCK_LINES_PER_TABLE):
        code_text = "\n".join(
            safe_lines[chunk_start:chunk_start + MAX_CODE_BLOCK_LINES_PER_TABLE]
        ).rstrip() or " "
        code_block = Preformatted(code_text, styles["code"])
        table = Table([[code_block]], colWidths=[16.5 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7f8fa")),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#d8d8d8")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        tables.append(table)
    return tables


def _wrap_code_line(line: str, max_chars: int = 92) -> list[str]:
    if len(line) <= max_chars:
        return [line]

    wrapped = []
    remaining = line
    continuation_indent = "  "
    while len(remaining) > max_chars:
        break_at = remaining.rfind(" ", 0, max_chars + 1)
        if break_at < max_chars // 2:
            break_at = max_chars
        wrapped.append(remaining[:break_at].rstrip())
        remaining = continuation_indent + remaining[break_at:].lstrip()
    wrapped.append(remaining)
    return wrapped


def _calculate_column_widths(rows: list[list[str]], total_width: float = 16.5 * cm) -> list[float]:
    column_count = max(len(row) for row in rows)
    if column_count == 1:
        return [total_width]

    weights = []
    for col_index in range(column_count):
        header = rows[0][col_index] if col_index < len(rows[0]) else ""
        cells = [row[col_index] if col_index < len(row) else "" for row in rows]
        max_len = max(len(_sanitize_text(cell)) for cell in cells)
        avg_len = sum(len(_sanitize_text(cell)) for cell in cells) / len(cells)
        weights.append(max(len(_sanitize_text(header)) * 1.5, avg_len, min(max_len, 42), 8))

    min_width = 1.8 * cm
    max_width = 6.8 * cm if column_count > 2 else 10 * cm
    raw_total = sum(weights)
    widths = [total_width * weight / raw_total for weight in weights]
    widths = [min(max(width, min_width), max_width) for width in widths]

    adjusted_total = sum(widths)
    if adjusted_total != total_width:
        scale = total_width / adjusted_total
        widths = [width * scale for width in widths]
    return widths


def _build_markdown_table(table_lines: list[str], styles: dict) -> Table:
    rows = [
        _split_table_row(line)
        for line in table_lines
        if not _is_table_separator(line)
    ]
    if not rows:
        return Table([[""]])

    column_count = max(len(row) for row in rows)
    normalized_rows = []
    for row_index, row in enumerate(rows):
        padded_row = row + [""] * (column_count - len(row))
        paragraph_style = styles["table_header"] if row_index == 0 else styles["table_cell"]
        normalized_rows.append(
            [Paragraph(_convert_markdown(cell), paragraph_style) for cell in padded_row]
        )

    table = Table(
        normalized_rows,
        colWidths=_calculate_column_widths(rows),
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8d8d8")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f8fa")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _build_header(ticker: str, styles: dict, data_str: str = None) -> list:
    """Monta o bloco de cabeçalho padrão."""
    if not data_str:
        data_str = datetime.now().strftime("%d/%m/%Y às %H:%M")
    story = []
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(_convert_markdown("Relatório de Análise de Investimento"), styles["titulo"]))
    story.append(Paragraph(_convert_markdown(f"Ativo: {_sanitize_text(ticker.upper())}"), styles["subtitulo"]))
    story.append(Paragraph(_convert_markdown(f"Gerado em {_sanitize_text(data_str)}"), styles["subtitulo"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a1a2e")))
    story.append(Spacer(1, 0.5*cm))

    aviso_texto = (
        "[!] Este relatório é gerado por inteligência artificial e tem caráter "
        "exclusivamente informativo. Não constitui recomendação de investimento. "
        "Consulte um assessor financeiro habilitado."
    )
    aviso = Table(
        [[Paragraph(escape(_sanitize_text(aviso_texto)), styles["aviso"])]],
        colWidths=[16.5*cm],
    )
    aviso.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#fff8e1")),
        ("TEXTCOLOR", (0,0), (-1,-1), colors.HexColor("#7a5c00")),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#f0c040")),
    ]))
    story.append(aviso)
    story.append(Spacer(1, 0.8*cm))
    return story


def _build_footer(story: list, styles: dict):
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        _convert_markdown("Gerado automaticamente pelo Investment Analyst Crew - Uso interno"),
        styles["rodape"]
    ))


def _build_pdf(filename: str, ticker: str, conteudo: str):
    """Gera PDF de um único ativo."""
    build_markdown_pdf(filename, ticker, conteudo)


def build_markdown_pdf(filename: str, ticker: str, conteudo: str):
    """Gera PDF de um relatório Markdown."""
    doc = SimpleDocTemplate(
        filename, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    styles = _get_styles()
    story = []
    story.extend(_build_header(ticker, styles))
    story.extend(_parse_conteudo(conteudo, styles))
    _build_footer(story, styles)
    doc.build(story)


def build_consolidated_pdf(resultados: list[dict], filename: str):
    """
    Gera PDF consolidado com múltiplos ativos.
    resultados = [{"ticker": "PETR4", "conteudo": "..."}, ...]
    """
    os.makedirs("outputs", exist_ok=True)
    doc = SimpleDocTemplate(
        filename, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    styles = _get_styles()
    story = []
    data_geracao = datetime.now().strftime("%d/%m/%Y às %H:%M")

    story.append(Spacer(1, 3*cm))
    story.append(Paragraph(_convert_markdown("Relatório Consolidado de Investimentos"), styles["titulo"]))
    story.append(Spacer(1, 0.4*cm))

    tickers_str = " - ".join([_sanitize_text(r["ticker"].upper()) for r in resultados])
    story.append(Paragraph(_convert_markdown(tickers_str), styles["subtitulo"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(_convert_markdown(f"Gerado em {_sanitize_text(data_geracao)}"), styles["subtitulo"]))
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a1a2e")))
    story.append(Spacer(1, 1*cm))

    story.append(Paragraph(_convert_markdown("Ativos Analisados"), styles["h1"]))
    story.append(Spacer(1, 0.3*cm))

    dados_tabela = [[
        Paragraph(_convert_markdown("#"), styles["table_header"]),
        Paragraph(_convert_markdown("Ticker"), styles["table_header"]),
        Paragraph(_convert_markdown("Análise gerada em"), styles["table_header"]),
    ]]
    for i, r in enumerate(resultados, 1):
        dados_tabela.append([
            Paragraph(_convert_markdown(str(i)), styles["table_cell"]),
            Paragraph(_convert_markdown(_sanitize_text(r["ticker"].upper())), styles["table_cell"]),
            Paragraph(_convert_markdown(_sanitize_text(data_geracao)), styles["table_cell"]),
        ])

    tabela = Table(dados_tabela, colWidths=[1*cm, 4*cm, 11.5*cm])
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1a1a2e")),
        ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#f5f5f5"), colors.white]),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#cccccc")),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ]))
    story.append(tabela)
    story.append(PageBreak())

    for i, resultado in enumerate(resultados):
        ticker = resultado["ticker"]
        conteudo = resultado["conteudo"]

        story.extend(_build_header(ticker, styles, data_geracao))
        story.extend(_parse_conteudo(conteudo, styles))
        _build_footer(story, styles)

        if i < len(resultados) - 1:
            story.append(PageBreak())

    doc.build(story)
