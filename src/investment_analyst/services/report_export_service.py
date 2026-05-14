from __future__ import annotations

import os
from datetime import datetime

def export_markdown_report_to_pdf(
    markdown_content: str,
    ticker: str,
    output_dir: str = "outputs",
) -> str:
    from investment_analyst.tools.pdf_generator_tool import build_markdown_pdf

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(output_dir, f"relatorio_{ticker}_{timestamp}.pdf")
    build_markdown_pdf(filename, ticker, markdown_content)
    return filename


def read_report_or_result(report_path: str, fallback_result: object) -> str:
    if os.path.exists(report_path):
        with open(report_path, encoding="utf-8") as report_file:
            return report_file.read()
    return str(fallback_result)
