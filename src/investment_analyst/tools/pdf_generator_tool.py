import os
from datetime import datetime
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

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
            spaceAfter=6, alignment=TA_CENTER,
        ),
        "subtitulo": ParagraphStyle(
            "Subtitulo", parent=styles["Normal"],
            fontSize=11, textColor=colors.HexColor("#4a4a6a"),
            spaceAfter=4, alignment=TA_CENTER,
        ),
        "h1": ParagraphStyle(
            "H1", parent=styles["Heading1"],
            fontSize=14, textColor=colors.HexColor("#1a1a2e"),
            spaceBefore=16, spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "H2", parent=styles["Heading2"],
            fontSize=12, textColor=colors.HexColor("#2e4057"),
            spaceBefore=10, spaceAfter=4,
        ),
        "corpo": ParagraphStyle(
            "Corpo", parent=styles["Normal"],
            fontSize=10, textColor=colors.HexColor("#2d2d2d"),
            leading=16, spaceAfter=6, alignment=TA_JUSTIFY,
        ),
        "bullet": ParagraphStyle(
            "Bullet", parent=styles["Normal"],
            fontSize=10, textColor=colors.HexColor("#2d2d2d"),
            leading=16, spaceAfter=4,
            leftIndent=16, firstLineIndent=-10,
        ),
        "rodape": ParagraphStyle(
            "Rodape", parent=styles["Normal"],
            fontSize=8, textColor=colors.HexColor("#888888"),
            alignment=TA_CENTER,
        ),
    }


def _parse_conteudo(conteudo: str, styles: dict) -> list:
    """Converte texto markdown-like em elementos ReportLab."""
    story = []
    for linha in conteudo.split("\n"):
        linha = linha.strip()
        if not linha:
            story.append(Spacer(1, 0.2*cm))
            continue

        if linha.startswith("# ") or (linha.isupper() and len(linha) < 60):
            texto = linha.lstrip("# ").strip()
            story.append(Paragraph(texto, styles["h1"]))
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
            continue

        if linha.startswith("## "):
            texto = linha.lstrip("# ").strip()
            story.append(Paragraph(texto, styles["h2"]))
            continue

        if linha.startswith("* ") or linha.startswith("- ") or linha.startswith("• "):
            texto = linha.lstrip("*-• ").strip()
            texto = _convert_markdown(texto)
            story.append(Paragraph(f"• {texto}", styles["bullet"]))
            continue

        if linha.startswith("**") and linha.endswith("**"):
            texto = linha.strip("*")
            story.append(Paragraph(f"<b>{texto}</b>", styles["corpo"]))
            continue

        texto = _convert_markdown(linha)
        story.append(Paragraph(texto, styles["corpo"]))

    return story


def _convert_markdown(texto: str) -> str:
    """Converte **negrito** e *itálico* para tags ReportLab."""
    import re
    texto = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', texto)
    texto = re.sub(r'\*(.+?)\*', r'<i>\1</i>', texto)
    return texto


def _build_header(ticker: str, styles: dict, data_str: str = None) -> list:
    """Monta o bloco de cabeçalho padrão."""
    if not data_str:
        data_str = datetime.now().strftime("%d/%m/%Y às %H:%M")
    story = []
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("Relatório de Análise de Investimento", styles["titulo"]))
    story.append(Paragraph(f"Ativo: {ticker.upper()}", styles["subtitulo"]))
    story.append(Paragraph(f"Gerado em {data_str}", styles["subtitulo"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a1a2e")))
    story.append(Spacer(1, 0.5*cm))

    aviso = Table(
        [["⚠  Este relatório é gerado por inteligência artificial e tem caráter exclusivamente "
          "\ninformativo. Não constitui recomendação de investimento. Consulte um assessor financeiro habilitado."]],
        colWidths=[16.5*cm],
    )
    aviso.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#fff8e1")),
        ("TEXTCOLOR", (0,0), (-1,-1), colors.HexColor("#7a5c00")),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("PADDING", (0,0), (-1,-1), 8),
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
        "Gerado automaticamente pelo Investment Analyst Crew • Uso interno",
        styles["rodape"]
    ))


def _build_pdf(filename: str, ticker: str, conteudo: str):
    """Gera PDF de um único ativo."""
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
    story.append(Paragraph("Relatório Consolidado de Investimentos", styles["titulo"]))
    story.append(Spacer(1, 0.4*cm))

    tickers_str = " • ".join([r["ticker"].upper() for r in resultados])
    story.append(Paragraph(tickers_str, styles["subtitulo"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(f"Gerado em {data_geracao}", styles["subtitulo"]))
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a1a2e")))
    story.append(Spacer(1, 1*cm))

    story.append(Paragraph("Ativos Analisados", styles["h1"]))
    story.append(Spacer(1, 0.3*cm))

    dados_tabela = [["#", "Ticker", "Análise gerada em"]]
    for i, r in enumerate(resultados, 1):
        dados_tabela.append([str(i), r["ticker"].upper(), data_geracao])

    tabela = Table(dados_tabela, colWidths=[1*cm, 4*cm, 11.5*cm])
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#f5f5f5"), colors.white]),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#cccccc")),
        ("PADDING", (0,0), (-1,-1), 8),
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