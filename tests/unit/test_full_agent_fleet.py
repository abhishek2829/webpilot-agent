"""Tests for WebPilot Agent — Full Agent Fleet (Phase 6).

Tests all new agents: ResearchAgent, SalesAgent, MarketingAgent,
FinanceAgent, ManagerAgent, and the pipeline system.
"""

import asyncio

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.agents.base import (
    AgentCapability,
    AgentRegistry,
    AgentResult,
    AgentStatus,
    AgentTask,
    BaseAgent,
)
from src.agents.research import ResearchAgent
from src.agents.sales import SalesAgent
from src.agents.marketing import MarketingAgent
from src.agents.finance import FinanceAgent
from src.agents.manager import ManagerAgent, Pipeline, PipelineStep, PipelineResult
from src.agents.dispatcher import AgentDispatcher


# =========================================================================
# Helpers
# =========================================================================

def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class MockAgent:
    """A simple mock agent for testing."""

    def __init__(self, name: str = "mock", actions: list[str] | None = None):
        self._name = name
        self._actions = actions or []
        self._status = AgentStatus.IDLE

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Mock {self._name}"

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [AgentCapability.BROWSER_AUTOMATION]

    @property
    def status(self) -> AgentStatus:
        return self._status

    async def execute(self, task: AgentTask) -> AgentResult:
        return AgentResult(
            task_id=task.task_id or "mock",
            agent_name=self._name,
            success=True,
            data={"extracted_variables": {"RESULT": f"from-{self._name}"}},
            duration_ms=50,
        )

    def can_handle(self, action: str) -> bool:
        return action in self._actions

    def get_actions(self) -> list[dict[str, str]]:
        return [{"name": a, "description": f"Mock {a}"} for a in self._actions]

    def get_stats(self) -> dict[str, int]:
        return {"total_tasks": 0}


# =========================================================================
# ResearchAgent
# =========================================================================

class TestResearchAgent:

    @pytest.fixture
    def agent(self) -> ResearchAgent:
        return ResearchAgent(workflows_dir=Path("workflows/research"))

    def test_implements_protocol(self, agent: ResearchAgent) -> None:
        assert isinstance(agent, BaseAgent)

    def test_name(self, agent: ResearchAgent) -> None:
        assert agent.name == "research"

    def test_description(self, agent: ResearchAgent) -> None:
        assert "research" in agent.description.lower()

    def test_capabilities(self, agent: ResearchAgent) -> None:
        assert AgentCapability.BROWSER_AUTOMATION in agent.capabilities
        assert AgentCapability.DATA_EXTRACTION in agent.capabilities

    def test_status_idle(self, agent: ResearchAgent) -> None:
        assert agent.status == AgentStatus.IDLE

    def test_unknown_action_fails(self, agent: ResearchAgent) -> None:
        result = run(agent.execute(AgentTask(action="nonexistent", task_id="t1")))
        assert not result.success
        assert "Unknown action" in (result.error or "")

    def test_get_stats(self, agent: ResearchAgent) -> None:
        stats = agent.get_stats()
        assert stats["total_tasks"] == 0


# =========================================================================
# SalesAgent
# =========================================================================

class TestSalesAgent:

    @pytest.fixture
    def agent(self) -> SalesAgent:
        return SalesAgent(workflows_dir=Path("workflows/sales"))

    def test_implements_protocol(self, agent: SalesAgent) -> None:
        assert isinstance(agent, BaseAgent)

    def test_name(self, agent: SalesAgent) -> None:
        assert agent.name == "sales"

    def test_description(self, agent: SalesAgent) -> None:
        assert "sales" in agent.description.lower()

    def test_capabilities(self, agent: SalesAgent) -> None:
        assert AgentCapability.BROWSER_AUTOMATION in agent.capabilities
        assert AgentCapability.FORM_FILLING in agent.capabilities

    def test_unknown_action_fails(self, agent: SalesAgent) -> None:
        result = run(agent.execute(AgentTask(action="nonexistent", task_id="t1")))
        assert not result.success


# =========================================================================
# MarketingAgent
# =========================================================================

class TestMarketingAgent:

    @pytest.fixture
    def agent(self) -> MarketingAgent:
        return MarketingAgent(workflows_dir=Path("workflows/marketing"))

    def test_implements_protocol(self, agent: MarketingAgent) -> None:
        assert isinstance(agent, BaseAgent)

    def test_name(self, agent: MarketingAgent) -> None:
        assert agent.name == "marketing"

    def test_description(self, agent: MarketingAgent) -> None:
        assert "marketing" in agent.description.lower()

    def test_capabilities(self, agent: MarketingAgent) -> None:
        assert AgentCapability.BROWSER_AUTOMATION in agent.capabilities

    def test_unknown_action_fails(self, agent: MarketingAgent) -> None:
        result = run(agent.execute(AgentTask(action="nonexistent", task_id="t1")))
        assert not result.success


# =========================================================================
# FinanceAgent
# =========================================================================

class TestFinanceAgent:

    @pytest.fixture
    def agent(self) -> FinanceAgent:
        return FinanceAgent(workflows_dir=Path("workflows/finance"))

    def test_implements_protocol(self, agent: FinanceAgent) -> None:
        assert isinstance(agent, BaseAgent)

    def test_name(self, agent: FinanceAgent) -> None:
        assert agent.name == "finance"

    def test_description(self, agent: FinanceAgent) -> None:
        assert "finance" in agent.description.lower()

    def test_capabilities(self, agent: FinanceAgent) -> None:
        assert AgentCapability.BROWSER_AUTOMATION in agent.capabilities
        assert AgentCapability.DATA_EXTRACTION in agent.capabilities

    def test_unknown_action_fails(self, agent: FinanceAgent) -> None:
        result = run(agent.execute(AgentTask(action="nonexistent", task_id="t1")))
        assert not result.success


# =========================================================================
# Full Registry with All Agents
# =========================================================================

class TestFullAgentRegistry:

    @pytest.fixture
    def full_registry(self) -> AgentRegistry:
        from src.agents.devops_setup import DevOpsSetupAgent
        reg = AgentRegistry()
        reg.register(DevOpsSetupAgent(workflows_dir=Path("workflows")))
        reg.register(ResearchAgent())
        reg.register(SalesAgent())
        reg.register(MarketingAgent())
        reg.register(FinanceAgent())
        return reg

    def test_all_agents_registered(self, full_registry: AgentRegistry) -> None:
        assert full_registry.count == 5
        assert "devops-setup" in full_registry.names
        assert "research" in full_registry.names
        assert "sales" in full_registry.names
        assert "marketing" in full_registry.names
        assert "finance" in full_registry.names

    def test_all_implement_protocol(self, full_registry: AgentRegistry) -> None:
        for name in full_registry.names:
            agent = full_registry.get(name)
            assert isinstance(agent, BaseAgent)
            assert agent.name == name
            assert len(agent.description) > 0
            assert len(agent.capabilities) > 0
            assert agent.status == AgentStatus.IDLE

    def test_find_browser_capable_agents(self, full_registry: AgentRegistry) -> None:
        agents = full_registry.find_by_capability(AgentCapability.BROWSER_AUTOMATION)
        assert len(agents) == 5  # All agents have browser automation


# =========================================================================
# ManagerAgent — Pipeline System
# =========================================================================

class TestManagerAgent:

    @pytest.fixture
    def dispatcher(self) -> AgentDispatcher:
        reg = AgentRegistry()
        reg.register(MockAgent(name="devops-setup", actions=["clerk-setup", "github-repo", "supabase-setup", "stripe-setup", "vercel-deploy"]))
        reg.register(MockAgent(name="research", actions=["lead-research", "competitor-analysis", "content-research"]))
        reg.register(MockAgent(name="sales", actions=["linkedin-connect", "crm-entry"]))
        reg.register(MockAgent(name="marketing", actions=["social-post", "blog-outline", "newsletter-setup"]))
        reg.register(MockAgent(name="finance", actions=["revenue-dashboard", "invoice-tracker", "payment-monitor", "subscription-audit"]))
        return AgentDispatcher(registry=reg)

    @pytest.fixture
    def manager(self, dispatcher: AgentDispatcher) -> ManagerAgent:
        return ManagerAgent(dispatcher=dispatcher)

    def test_implements_protocol(self, manager: ManagerAgent) -> None:
        assert isinstance(manager, BaseAgent)

    def test_name(self, manager: ManagerAgent) -> None:
        assert manager.name == "manager"

    def test_description(self, manager: ManagerAgent) -> None:
        assert "orchestrat" in manager.description.lower()

    def test_list_pipelines(self, manager: ManagerAgent) -> None:
        pipelines = manager.list_pipelines()
        assert len(pipelines) >= 4
        names = [p["name"] for p in pipelines]
        assert "full-saas-setup" in names
        assert "outbound-pipeline" in names
        assert "content-launch" in names
        assert "revenue-health-check" in names

    def test_can_handle_builtin_pipelines(self, manager: ManagerAgent) -> None:
        assert manager.can_handle("full-saas-setup")
        assert manager.can_handle("outbound-pipeline")
        assert not manager.can_handle("nonexistent")

    def test_run_full_saas_setup(self, manager: ManagerAgent) -> None:
        result = run(manager.run_pipeline(
            "full-saas-setup",
            {"project_name": "TestApp", "repo_name": "test-app"},
        ))
        assert result.pipeline_name == "full-saas-setup"
        assert len(result.step_results) == 5
        assert result.success

    def test_run_outbound_pipeline(self, manager: ManagerAgent) -> None:
        result = run(manager.run_pipeline(
            "outbound-pipeline",
            {"company_url": "https://example.com"},
        ))
        assert result.pipeline_name == "outbound-pipeline"
        assert len(result.step_results) == 3

    def test_run_content_launch(self, manager: ManagerAgent) -> None:
        result = run(manager.run_pipeline(
            "content-launch",
            {"search_keyword": "AI agents"},
        ))
        assert result.pipeline_name == "content-launch"
        assert len(result.step_results) == 4

    def test_run_revenue_health_check(self, manager: ManagerAgent) -> None:
        result = run(manager.run_pipeline("revenue-health-check"))
        assert result.pipeline_name == "revenue-health-check"
        assert len(result.step_results) == 4

    def test_unknown_pipeline_fails(self, manager: ManagerAgent) -> None:
        result = run(manager.run_pipeline("nonexistent"))
        assert not result.success
        assert "not found" in (result.error or "").lower()

    def test_execute_via_agent_protocol(self, manager: ManagerAgent) -> None:
        task = AgentTask(action="full-saas-setup", parameters={"project_name": "TestApp"}, task_id="exec-1")
        result = run(manager.execute(task))
        assert result.success
        assert result.agent_name == "manager"

    def test_custom_pipeline(self, manager: ManagerAgent) -> None:
        custom = Pipeline(
            name="custom-test",
            description="Test pipeline",
            steps=[
                PipelineStep(action="clerk-setup", agent_name="devops-setup"),
                PipelineStep(action="lead-research", agent_name="research"),
            ],
        )
        result = run(manager.run_custom_pipeline(custom, {"project_name": "Test"}))
        assert result.success
        assert len(result.step_results) == 2

    def test_register_custom_pipeline(self, manager: ManagerAgent) -> None:
        custom = Pipeline(name="my-pipeline", description="Custom", steps=[
            PipelineStep(action="clerk-setup", agent_name="devops-setup"),
        ])
        manager.register_pipeline(custom)
        assert manager.can_handle("my-pipeline")

    def test_pipeline_stats(self, manager: ManagerAgent) -> None:
        run(manager.run_pipeline("full-saas-setup", {"project_name": "Test"}))
        stats = manager.get_stats()
        assert stats["total_pipelines"] == 1
        assert stats["completed"] == 1
        assert stats["total_steps_executed"] == 5

    def test_pipeline_history(self, manager: ManagerAgent) -> None:
        run(manager.run_pipeline("full-saas-setup", {"project_name": "Test"}))
        history = manager.get_history()
        assert len(history) == 1
        assert history[0]["pipeline_name"] == "full-saas-setup"

    def test_pipeline_result_to_dict(self, manager: ManagerAgent) -> None:
        result = run(manager.run_pipeline("full-saas-setup", {"project_name": "Test"}))
        d = result.to_dict()
        assert "pipeline_name" in d
        assert "step_results" in d
        assert "total_duration_ms" in d
        assert d["steps_completed"] == 5

    def test_input_mapping_between_steps(self, manager: ManagerAgent) -> None:
        """Test that data flows between pipeline steps via input_mapping."""
        custom = Pipeline(
            name="mapping-test",
            description="Test input mapping",
            steps=[
                PipelineStep(action="lead-research", agent_name="research"),
                PipelineStep(
                    action="linkedin-connect",
                    agent_name="sales",
                    input_mapping={"prospect_name": "step_0.RESULT"},
                ),
            ],
        )
        result = run(manager.run_custom_pipeline(custom))
        assert result.success
        assert len(result.step_results) == 2

    def test_conditional_step(self, manager: ManagerAgent) -> None:
        """Test that conditional steps are skipped when condition is not met."""
        custom = Pipeline(
            name="condition-test",
            description="Test conditions",
            steps=[
                PipelineStep(action="lead-research", agent_name="research"),
                PipelineStep(
                    action="crm-entry",
                    agent_name="sales",
                    condition="step_0.success == false",  # Will skip — step_0 succeeds
                ),
            ],
        )
        result = run(manager.run_custom_pipeline(custom))
        # Only 1 step executed (step 1 skipped due to condition)
        assert len(result.step_results) == 1

    def test_get_lessons_empty(self, manager: ManagerAgent) -> None:
        run(manager.run_pipeline("full-saas-setup", {"project_name": "Test"}))
        lessons = manager.get_lessons()
        assert lessons == []
