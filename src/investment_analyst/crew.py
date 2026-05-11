import os
from crewai import Agent, Task, Crew, Process, LLM


from dotenv import load_dotenv
load_dotenv()
llm = LLM(
    model="openrouter/stepfun/step-3.5-flash:free",
    temperature=0.2,
    max_tokens=4096,
)


from .tools.financial_data_tool import FinancialDataTool
from .tools.news_scraper_tool import NewsScraperTool
from .tools.pdf_generator_tool import PDFGeneratorTool


class InvestmentAnalystCrew:
    def crew(self) -> Crew:
        financial_tool = FinancialDataTool()
        news_tool = NewsScraperTool()
        pdf_tool = PDFGeneratorTool()

        data_collector = Agent(
            role="Coletor de Dados Financeiros",
            goal="Coletar, validar e estruturar dados financeiros completos e atualizados do ativo {ticker}. Garantir consistência, remover inconsistências e entregar os dados organizados em formato estruturado.",
            backstory="Especialista em engenharia de dados financeiros, com experiência em integração de múltiplas APIs de mercado. Atua garantindo qualidade, integridade e padronização dos dados antes da análise. Foca em entregar dados prontos para análise, eliminando ruídos e inconsistências que possam comprometer a qualidade da análise subsequente. Utiliza ferramentas avançadas de coleta e validação para garantir que os dados sejam confiáveis e relevantes para a análise fundamentalista.",
            tools=[financial_tool],
            verbose=True,
            llm=llm,
        )

        fundamental_analyst = Agent(
            role="Analista Fundamentalista Sênior",
            goal="Realizar análise fundamentalista profunda do ativo {ticker}, avaliando crescimento, lucratividade, eficiência operacional, estrutura de capital, geração de caixa e valuation. Classificar a empresa como: Forte, Moderada ou Fraca em fundamentos.",
            backstory="Investidor com 20 anos de experiência em análise de empresas listadas. Especialista em valuation, análise de múltiplos, fluxo de caixa descontado e identificação de empresas com vantagens competitivas sustentáveis. Foca em identificar oportunidades de investimento de longo prazo, avaliando a qualidade dos fundamentos e a capacidade de geração de valor da empresa ao longo do tempo. Utiliza uma abordagem rigorosa e detalhada para garantir que a análise seja precisa e relevante para a tomada de decisão de investimento.",
            verbose=True,
            llm=llm,
        )

        sentiment_analyst = Agent(
            role="Analista de Sentimento de Mercado",
            goal="Avaliar o sentimento do mercado sobre {ticker} utilizando notícias recentes, eventos corporativos, contexto macroeconômico e percepção de analistas. Identificar riscos emergentes e tendências narrativas. Classificar o sentimento como: Positivo, Neutro ou Negativo.",
            backstory="Especialista em análise de narrativa de mercado. Detecta padrões emocionais e mudanças de percepção antes que impactem o preço. Utiliza análise qualitativa e quantitativa para classificar o sentimento como: Positivo, Neutro ou Negativo. Foca em identificar riscos emergentes e oportunidades ocultas que podem não ser evidentes na análise fundamentalista tradicional, fornecendo uma visão mais completa do cenário de investimento. Utiliza uma abordagem holística para entender como as notícias e eventos estão moldando a percepção do mercado sobre o ativo, ajudando a antecipar movimentos de preço e identificar oportunidades de investimento que podem ser perdidas por análises mais tradicionais.",
            tools=[news_tool],
            verbose=True,
            llm=llm,
        )

        risk_manager = Agent(
            role="Gestor de Risco",
            goal="Consolidar análise fundamentalista e análise de sentimento para classificar o risco global do investimento em {ticker}. Avaliar risco financeiro, risco operacional, risco macroeconômico e risco reputacional. Gerar score de risco de 0 a 100.",
            backstory="Especialista em gestão de risco institucional. Utiliza metodologia quantitativa e qualitativa para classificar ativos sob perspectiva conservadora. Foca em preservação de capital e identificação de riscos ocultos que podem impactar o investimento. Utiliza uma abordagem holística para avaliar o risco, considerando não apenas os aspectos financeiros, mas também os riscos operacionais, macroeconômicos e reputacionais que podem afetar o desempenho do investimento. Fornece uma classificação de risco clara e objetiva, ajudando os investidores a tomar decisões informadas e alinhadas com seus objetivos de investimento e tolerância ao risco.",
            verbose=True,
            llm=llm,
        )

        report_generator = Agent(
            role="Redator de Relatórios de Investimento",
            goal="Gerar relatório estruturado, claro e acionável sobre {ticker}, integrando análise fundamentalista, sentimento de mercado e classificação de risco. Produzir recomendação final: Comprar, Manter ou Evitar. Garantir que o relatório seja compreensível para investidores de todos os níveis, destacando os pontos-chave e justificativas de forma objetiva.",
            backstory="Especialista em comunicação financeira. Traduz análises técnicas complexas em relatórios objetivos utilizados por investidores estratégicos. Foca em clareza, concisão e relevância para tomada de decisão. Utiliza uma abordagem estruturada para garantir que o relatório seja fácil de entender, mesmo para investidores que não possuem um conhecimento profundo de análise financeira. Destaca os pontos-chave e as justificativas de forma objetiva, ajudando os investidores a tomar decisões informadas com base na análise apresentada. Utiliza ferramentas avançadas de formatação e apresentação para garantir que o relatório seja visualmente atraente e fácil de navegar.",
            tools=[pdf_tool],
            verbose=True,
            llm=llm,
        )

        collect_task = Task(
            description="Use a ferramenta financial_data_fetcher para coletar os dados do ativo {ticker}. Retorne os dados brutos estruturados sem análise.",
            expected_output="Dados financeiros de {ticker}: preço, variação, P/L, DY, market cap, volume, máxima e mínima de 52 semanas.",
            agent=data_collector,
        )

        fundamental_task = Task(
            description="Com os dados coletados, analise os fundamentos de {ticker}. Cubra: valuation (P/L, DY), saúde financeira, crescimento, riscos do setor e posicionamento competitivo. Seja direto e aponte oportunidades e armadilhas.",
            expected_output="Análise fundamentalista de {ticker} cobrindo: valuation, saúde financeira, crescimento, riscos do setor e conclusão com classificação (Fraca/Moderada/Forte).",
            agent=fundamental_analyst,
            context=[collect_task],
        )

        sentiment_task = Task(
            description="Use a ferramenta news_scraper para buscar notícias recentes de {ticker}. Classifique cada notícia como Positiva, Negativa ou Neutra. Identifique a narrativa dominante e eventos de risco emergentes.",
            expected_output="Lista das principais notícias de {ticker} com classificação de sentimento, sentimento geral (Positivo/Neutro/Negativo) e principais riscos identificados.",
            agent=sentiment_analyst,
        )

        risk_task = Task(
            description="Consolide a análise fundamentalista e o sentimento de {ticker}. Avalie: risco financeiro, operacional, macroeconômico e reputacional. Produza uma classificação final com score numérico e justificativa.",
            expected_output="Classificação de risco de {ticker}: Baixo/Moderado/Alto, score de 0 a 100, e justificativa objetiva por categoria de risco.",
            agent=risk_manager,
            context=[fundamental_task, sentiment_task],
        )

        report_task = Task(
            description="""
            Escreva o relatório final de {ticker} em português com as seções abaixo. 
                "Use markdown: # para títulos principais, ## para subtítulos, **negrito** para destaques, 
                "- para bullets.
                "Seções obrigatórias:
                "# RESUMO EXECUTIVO
                "# DADOS DO ATIVO
                "# ANÁLISE FUNDAMENTALISTA
                "# ANÁLISE DE SENTIMENTO E NOTÍCIAS
                "# GESTÃO DE RISCO
                "# RECOMENDAÇÃO FINAL
                "Ao final, chame a ferramenta pdf_generator com:
                "- ticker: {ticker}
                "- conteudo: o relatório completo escrito acima""",
            expected_output="Confirmação de que o PDF foi gerado em outputs/ com o caminho completo do arquivo.",
            agent=report_generator,
            context=[collect_task, fundamental_task, sentiment_task, risk_task],
        )

        return Crew(
            agents=[data_collector, fundamental_analyst, sentiment_analyst, risk_manager, report_generator],
            tasks=[collect_task, fundamental_task, sentiment_task, risk_task, report_task],
            process=Process.sequential,
            verbose=True,
            llm=llm,
        )