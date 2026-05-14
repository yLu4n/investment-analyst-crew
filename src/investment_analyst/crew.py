from dotenv import load_dotenv

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from investment_analyst.config.llm import get_llm
from investment_analyst.tools.financial_data_tool import FinancialDataTool
from investment_analyst.tools.news_scraper_tool import NewsScraperTool
from investment_analyst.tools.pdf_generator_tool import PDFGeneratorTool


load_dotenv()


@CrewBase
class InvestmentAnalystCrew:

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"
    
    llm = get_llm()

    def __init__(self, report_output_path: str = "outputs/investment_report.md"):
        self.financial_data_tool = FinancialDataTool()
        self.news_scraper_tool = NewsScraperTool()
        self.pdf_generator_tool = PDFGeneratorTool()
        self.report_output_path = report_output_path

    @agent
    def data_collector(self) -> Agent:
        return Agent(
            config=self.agents_config["data_collector"],
            tools=[self.financial_data_tool],
            llm=self.llm,
            verbose=True,
        )

    @agent
    def fundamental_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["fundamental_analyst"],
            tools=[self.financial_data_tool],
            llm=self.llm,
            verbose=True,
        )

    @agent
    def sentiment_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["sentiment_analyst"],
            tools=[self.news_scraper_tool],
            llm=self.llm,
            verbose=True,
        )

    @agent
    def risk_manager(self) -> Agent:
        return Agent(
            config=self.agents_config["risk_manager"],
            llm=self.llm,
            verbose=True,
        )

    @agent
    def financial_planner(self) -> Agent:
        return Agent(
            config=self.agents_config["financial_planner"],
            llm=self.llm,
            verbose=True,
        )

    @agent
    def recommendation_validator(self) -> Agent:
        return Agent(
            config=self.agents_config["recommendation_validator"],
            llm=self.llm,
            verbose=True,
        )

    @agent
    def report_generator(self) -> Agent:
        return Agent(
            config=self.agents_config["report_generator"],
            tools=[self.pdf_generator_tool],
            llm=self.llm,
            verbose=True,
        )

    @task
    def collect_financial_data_task(self) -> Task:
        return Task(
            config=self.tasks_config["collect_financial_data_task"],
            agent=self.data_collector(),
        )

    @task
    def fundamental_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config["fundamental_analysis_task"],
            agent=self.fundamental_analyst(),
        )

    @task
    def sentiment_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config["sentiment_analysis_task"],
            agent=self.sentiment_analyst(),
        )

    @task
    def risk_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config["risk_analysis_task"],
            agent=self.risk_manager(),
        )

    @task
    def financial_planning_task(self) -> Task:
        return Task(
            config=self.tasks_config["financial_planning_task"],
            agent=self.financial_planner(),
        )

    @task
    def recommendation_validation_task(self) -> Task:
        return Task(
            config=self.tasks_config["recommendation_validation_task"],
            agent=self.recommendation_validator(),
        )

    @task
    def final_report_task(self) -> Task:
        return Task(
            config=self.tasks_config["final_report_task"],
            agent=self.report_generator(),
            output_file=self.report_output_path,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
