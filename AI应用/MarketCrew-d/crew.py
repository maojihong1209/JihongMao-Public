# 第三方包
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

# 本地模块
from models import PMOutput, ResearchReport, MarketStrategy, CampaignIdea, Copy, ReviewResult


@CrewBase
class MarketCrew():
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    def __init__(self, llm, progress_callback=None):
        self.llm = llm
        self.progress_callback = progress_callback

    # ---- Agents ----

    @agent
    def project_manager(self) -> Agent:
        return Agent(
            config=self.agents_config['project_manager'],
            verbose=True,
            llm=self.llm,
            tools=[SerperDevTool()],
        )

    @agent
    def market_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config['market_analyst'],
            verbose=True,
            llm=self.llm,
            tools=[SerperDevTool(), ScrapeWebsiteTool()],
        )

    @agent
    def marketing_strategist(self) -> Agent:
        return Agent(
            config=self.agents_config['marketing_strategist'],
            verbose=True,
            llm=self.llm,
            tools=[SerperDevTool(), ScrapeWebsiteTool()],
        )

    @agent
    def content_creator(self) -> Agent:
        return Agent(
            config=self.agents_config['content_creator'],
            verbose=True,
            llm=self.llm,
            tools=[SerperDevTool()],
        )

    @agent
    def content_reviewer(self) -> Agent:
        return Agent(
            config=self.agents_config['content_reviewer'],
            verbose=True,
            llm=self.llm,
            tools=[SerperDevTool()],
        )

    # ---- Tasks ----

    @task
    def pm_task(self) -> Task:
        return Task(
            config=self.tasks_config['pm_task'],
            output_json=PMOutput,
            callback=self.progress_callback,
        )

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config['research_task'],
            context=[self.pm_task()],
            output_json=ResearchReport,
            callback=self.progress_callback,
        )

    @task
    def strategy_task(self) -> Task:
        return Task(
            config=self.tasks_config['strategy_task'],
            context=[self.pm_task(), self.research_task()],
            output_json=MarketStrategy,
            callback=self.progress_callback,
        )

    @task
    def campaign_idea_task(self) -> Task:
        return Task(
            config=self.tasks_config['campaign_idea_task'],
            context=[self.strategy_task()],
            output_json=CampaignIdea,
            callback=self.progress_callback,
        )

    @task
    def copy_creation_task(self) -> Task:
        return Task(
            config=self.tasks_config['copy_creation_task'],
            context=[self.strategy_task(), self.campaign_idea_task()],
            output_json=Copy,
            callback=self.progress_callback,
        )

    @task
    def review_task(self) -> Task:
        return Task(
            config=self.tasks_config['review_task'],
            context=[self.campaign_idea_task(), self.copy_creation_task(), self.strategy_task()],
            output_json=ReviewResult,
            callback=self.progress_callback,
        )

    # ---- Crew ----

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
