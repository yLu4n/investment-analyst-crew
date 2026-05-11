import sys
import os

from dotenv import load_dotenv
load_dotenv()

from investment_analyst.crew import InvestmentAnalystCrew
from investment_analyst.tools.pdf_generator_tool import build_consolidated_pdf
from datetime import datetime

def carregar_tickers_arquivo(caminho:str) -> list[str]:
    tickers = []
    
    with open(caminho, "r") as f:
        for linha in f:
            linha = linha.strip()
            
            if linha and not linha.startswith("#"):
                continue
            
            for t in linha.replace(",", " ").split():
                tickers.append(t.upper().replace(".SA", ""))
    
    return tickers

def resolver_tickers(args: list[str]) -> list[str]:
    if not args:
        return ["PETR4"]
    
    if len(args) == 1 and os.path.isfile(args[0]):
        tickers = carregar_tickers_arquivo(args[0])
        print(f"Arquivo carregado: {args[0]}")
        print(f"Tickers encontrados: {', '.join(tickers)}")
        return tickers
    
    return [t.upper().replace(".SA", "") for t in args]

def analisar_ativo(ticker: str) -> dict:
    print(f"\n{'='*60}")
    print(f" Analisando ativo: {ticker}")
    print(f"{'='*60}")
    result = InvestmentAnalystCrew().crew().kickoff(inputs={"ticker": ticker})
    return {
        "ticker": ticker,
        "conteudo": str(result),
    }

def run():
    args = sys.argv[1:]
    tickers = resolver_tickers(args)
    
    if not tickers:
        print("Nenhum ticker encontrado. Uso: ")
        print(" uv run python -m investment_analyst.main TICKER1 TICKER2")
        print(" uv run python -m investment_analyst.main ativos.txt")
        sys.exit(1)
        
    print(f"\n Investmente Analyst Crew")
    print(f"Ativos para análise: {', '.join(tickers)}")
    print(f"Total: {len(tickers)} ativo(s)\n")
    
    resultados = []
    erros = []
    
    for i, ticker in enumerate(tickers, 1):
        print(f"\n[{i}/{len(tickers)}] Iniciando análise de {ticker}...")
        try:
            resultado = analisar_ativo(ticker)
            resultados.append(resultado)
            print(f"Análise de {ticker} concluída com sucesso.")
        except Exception as e:
            print(f"Erro ao analisar {ticker}: {e}")
            erros.append({"ticker": ticker, "erro": str(e)})
            
    
    if resultados:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tickers_str = "_".join([r["ticker"] for r in resultados])
        filename = f"outputs/relatorio_consolidado_{tickers_str}_{timestamp}.pdf"
        
        print(f"\n Gerando Realatório...")
        build_consolidated_pdf(resultados, filename)
        print(f"Relatório gerado com sucesso: {filename}")
    
    
    print(f"\n{'='*60}")
    print(f"  RESUMO DA EXECUÇÃO")
    print(f"{'='*60}")
    print(f"  Analisados com sucesso: {len(resultados)}")
    print(f"  Com erro:              {len(erros)}")
    if erros:
        for e in erros:
            print(f"     - {e['ticker']}: {e['erro']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run()