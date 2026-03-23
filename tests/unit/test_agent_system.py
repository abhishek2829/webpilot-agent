"""Tests for WebPilot Agent — Multi-Agent System (Phase 5).

Tests the agent framework: BaseAgent protocol, AgentRegistry,
DevOpsSetupAgent, AgentDispatcher, and BrowserSessionPool.
"""

import asyncio

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.base import (
    AgentCapability,
    AgentRegistry,
    AgentResult,
    AgentStatus,
    AgentTask,
    BaseAgent,
)
from src.agents.devops_setup import DevOpsSetupAgent
from src.agents.dispatcher import AgentDispatcher, DispatchError
from src.browser.session_pool import BrowserSessionPool


# =========================================================================
# Helpers
# =========================================================================

def run(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class MockAgent:
    """A simple mock agent implementing the BaseAgent protocol."""

    def __init__(
        self,
        name: str = "mock-agent",
        actions: list[str] | None = None,
    ) -> None:
        self._name = name
        self._actions = actions or ["test-action"]
        self._status = AgentStatus.IDLE

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Mock agent: {self._name}"

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [AgentCapability.BROWSER_AUTOMATION]

    @property
    def status(self) -> AgentStatus:
        return self._status

    async def execute(self, task: AgentTask) -> AgentResult:
        return AgentResult(
            task_id=task.task_id or "mock-task",
            agent_name=self._name,
            success=True,
            data={"mock": True},
            duration_ms=100,
        )

    def can_handle(self, action: str) -> bool:
        return action in self._actions

    def get_actions(self) -> list[dict[str, str]]:
        return [{"name": a, "description": f"Mock action {a}"} for a in self._actions]

    def get_stats(self) -> dict[str, int]:
        return {"total_tasks": 0}


class OfflineAgent(MockAgent):
    """Mock agent that is offline."""

    @property
    def status(self) -> AgentStatus:
        return AgentStatus.OFFLINE


class FailingAgent(MockAgent):
    """Mock agent that always fails."""

    async def execute(self, task: AgentTask) -> AgentResult:
        raise RuntimeError("Agent crashed")


# =========================================================================
# BaseAgent Protocol
# =========================================================================

class TestBaseAgentProtocol:
    """Test that the BaseAgent protocol works correctly."""

    def test_mock_agent_implements_protocol(self) -> None:
        agent = MockAgent()
        assert isinstance(agent, BaseAgent)

    def test_protocol_properties(self) -> None:
        agent = MockAgent(name="test-agent")
        assert agent.name == "test-agent"
        assert agent.description == "Mock agent: test-agent"
        assert AgentCapability.BROWSER_AUTOMATION in agent.capabilities
        assert agent.status == AgentStatus.IDLE

    def test_can_handle(self) -> None:
        agent = MockAgent(actions=["clerk-setup", "vercel-deploy"])
        assert agent.can_handle("clerk-setup")
        assert not agent.can_handle("unknown-action")

    def test_get_actions(self) -> None:
        agent = MockAgent(actions=["a", "b"])
        actions = agent.get_actions()
        assert len(actions) == 2
        assert actions[0]["name"] == "a"

    def test_execute_returns_result(self) -> None:
        agent = MockAgent()
        task = AgentTask(action="test-action", task_id="t1")
        result = run(agent.execute(task))
        assert result.success
        assert result.agent_name == "mock-agent"


# =========================================================================
# AgentTask & AgentResult
# =========================================================================

class TestAgentModels:
    """Test AgentTask and AgentResult data classes."""

    def test_agent_task_defaults(self) -> None:
        task = AgentTask(action="clerk-setup")
        assert task.action == "clerk-setup"
        assert task.checkpoint_mode == "auto"
        assert task.headless is True
        assert task.parameters == {}

    def test_agent_result_to_dict(self) -> None:
        result = AgentResult(
            task_id="t1",
            agent_name="devops",
            success=True,
            data={"key": "value"},
            duration_ms=500,
        )
        d = result.to_dict()
        assert d["task_id"] == "t1"
        assert d["success"] is True
        assert d["data"] == {"key": "value"}
        assert "error" not in d

    def test_agent_result_with_error(self) -> None:
        result = AgentResult(
            task_id="t2",
            agent_name="devops",
            success=False,
            error="Something went wrong",
        )
        d = result.to_dict()
        assert d["error"] == "Something went wrong"


# =========================================================================
# AgentRegistry
# =========================================================================

class TestAgentRegistry:
    """Test agent registration and discovery."""

    def test_register_agent(self) -> None:
        reg = AgentRegistry()
        agent = MockAgent()
        reg.register(agent)
        assert reg.count == 1
        assert reg.exists("mock-agent")

    def test_register_duplicate_raises(self) -> None:
        reg = AgentRegistry()
        reg.register(MockAgent())
        with pytest.raises(ValueError, match="already registered"):
            reg.register(MockAgent())

    def test_get_agent(self) -> None:
        reg = AgentRegistry()
        reg.register(MockAgent(name="agent-1"))
        agent = reg.get("agent-1")
        assert agent.name == "agent-1"

    def test_get_nonexistent_raises(self) -> None:
        reg = AgentRegistry()
        with pytest.raises(KeyError, match="not found"):
            reg.get("nope")

    def test_unregister(self) -> None:
        reg = AgentRegistry()
        reg.register(MockAgent())
        reg.unregister("mock-agent")
        assert reg.count == 0

    def test_list_agents(self) -> None:
        reg = AgentRegistry()
        reg.register(MockAgent(name="alpha"))
        reg.register(MockAgent(name="beta"))
        listing = reg.list_agents()
        assert len(listing) == 2
        names = [a["name"] for a in listing]
        assert names == ["alpha", "beta"]

    def test_find_by_capability(self) -> None:
        reg = AgentRegistry()
        reg.register(MockAgent(name="browser-agent"))
        agents = reg.find_by_capability(AgentCapability.BROWSER_AUTOMATION)
        assert len(agents) == 1
        assert agents[0].name == "browser-agent"

    def test_find_by_capability_empty(self) -> None:
        reg = AgentRegistry()
        reg.register(MockAgent())
        agents = reg.find_by_capability(AgentCapability.DNS_MANAGEMENT)
        assert agents == []

    def test_find_for_action(self) -> None:
        reg = AgentRegistry()
        reg.register(MockAgent(name="devops", actions=["clerk-setup"]))
        reg.register(MockAgent(name="research", actions=["web-search"]))
        agent = reg.find_for_action("clerk-setup")
        assert agent is not None
        assert agent.name == "devops"

    def test_find_for_action_none(self) -> None:
        reg = AgentRegistry()
        reg.register(MockAgent(actions=["a"]))
        assert reg.find_for_action("unknown") is None

    def test_names_sorted(self) -> None:
        reg = AgentRegistry()
        reg.register(MockAgent(name="charlie"))
        reg.register(MockAgent(name="alpha"))
        assert reg.names == ["alpha", "charlie"]

    def test_registration_log(self) -> None:
        reg = AgentRegistry()
        reg.register(MockAgent(name="logged"))
        log = reg.get_registration_log()
        assert len(log) == 1
        assert log[0]["agent_name"] == "logged"


# =========================================================================
# DevOpsSetupAgent
# =========================================================================

class TestDevOpsSetupAgent:
    """Test the DevOps Setup Agent (first concrete agent)."""

    @pytest.fixture
    def agent(self) -> DevOpsSetupAgent:
        return DevOpsSetupAgent(workflows_dir=Path("workflows"))

    def test_implements_protocol(self, agent: DevOpsSetupAgent) -> None:
        assert isinstance(agent, BaseAgent)

    def test_name(self, agent: DevOpsSetupAgent) -> None:
        assert agent.name == "devops-setup"

    def test_description(self, agent: DevOpsSetupAgent) -> None:
        assert "DevOps" in agent.description

    def test_capabilities(self, agent: DevOpsSetupAgent) -> None:
        caps = agent.capabilities
        assert AgentCapability.BROWSER_AUTOMATION in caps
        assert AgentCapability.ACCOUNT_SETUP in caps
        assert AgentCapability.API_KEY_EXTRACTION in caps

    def test_status_starts_idle(self, agent: DevOpsSetupAgent) -> None:
        assert agent.status == AgentStatus.IDLE

    def test_can_handle_known_workflows(self, agent: DevOpsSetupAgent) -> None:
        assert agent.can_handle("clerk-setup")
        assert agent.can_handle("vercel-deploy")
        assert agent.can_handle("supabase-setup")
        assert agent.can_handle("stripe-setup")
        assert agent.can_handle("github-repo")
        assert agent.can_handle("domain-setup")

    def test_cannot_handle_unknown(self, agent: DevOpsSetupAgent) -> None:
        assert not agent.can_handle("unknown-workflow")

    def test_get_actions(self, agent: DevOpsSetupAgent) -> None:
        actions = agent.get_actions()
        assert len(actions) >= 6
        action_names = [a["name"] for a in actions]
        assert "clerk-setup" in action_names
        assert "vercel-deploy" in action_names

    def test_get_stats_initial(self, agent: DevOpsSetupAgent) -> None:
        stats = agent.get_stats()
        assert stats["total_tasks"] == 0
        assert stats["completed"] == 0
        assert stats["failed"] == 0

    def test_execute_unknown_action_fails(self, agent: DevOpsSetupAgent) -> None:
        task = AgentTask(action="nonexistent-workflow", task_id="t1")
        result = run(agent.execute(task))
        assert not result.success
        assert "Unknown action" in (result.error or "")
        assert agent.get_stats()["failed"] == 1

    def test_get_lessons_empty(self, agent: DevOpsSetupAgent) -> None:
        assert agent.get_lessons() == []


# =========================================================================
# AgentDispatcher
# =========================================================================

class TestAgentDispatcher:
    """Test task dispatch and routing."""

    @pytest.fixture
    def dispatcher(self) -> AgentDispatcher:
        reg = AgentRegistry()
        reg.register(MockAgent(name="devops", actions=["clerk-setup", "vercel-deploy"]))
        reg.register(MockAgent(name="research", actions=["web-search"]))
        return AgentDispatcher(registry=reg)

    def test_dispatch_auto_routes(self, dispatcher: AgentDispatcher) -> None:
        task = AgentTask(action="clerk-setup")
        result = run(dispatcher.dispatch(task))
        assert result.success
        assert result.agent_name == "devops"

    def test_dispatch_to_specific_agent(self, dispatcher: AgentDispatcher) -> None:
        task = AgentTask(action="web-search")
        result = run(dispatcher.dispatch_to("research", task))
        assert result.success
        assert result.agent_name == "research"

    def test_dispatch_unknown_action_raises(self, dispatcher: AgentDispatcher) -> None:
        task = AgentTask(action="unknown")
        with pytest.raises(DispatchError, match="No agent"):
            run(dispatcher.dispatch(task))

    def test_dispatch_unknown_agent_raises(self, dispatcher: AgentDispatcher) -> None:
        task = AgentTask(action="test")
        with pytest.raises(DispatchError, match="not found"):
            run(dispatcher.dispatch_to("nonexistent", task))

    def test_dispatch_assigns_task_id(self, dispatcher: AgentDispatcher) -> None:
        task = AgentTask(action="clerk-setup")
        result = run(dispatcher.dispatch(task))
        assert result.task_id.startswith("task-")

    def test_dispatch_stores_result(self, dispatcher: AgentDispatcher) -> None:
        task = AgentTask(action="clerk-setup", task_id="stored-1")
        run(dispatcher.dispatch(task))
        result = dispatcher.get_result("stored-1")
        assert result is not None
        assert result.success

    def test_get_result_not_found(self, dispatcher: AgentDispatcher) -> None:
        assert dispatcher.get_result("nope") is None

    def test_dispatch_offline_agent(self) -> None:
        reg = AgentRegistry()
        reg.register(OfflineAgent(name="offline", actions=["test"]))
        dispatcher = AgentDispatcher(registry=reg)
        task = AgentTask(action="test", agent_name="offline")
        result = run(dispatcher.dispatch(task))
        assert not result.success
        assert "offline" in (result.error or "").lower()

    def test_dispatch_failing_agent(self) -> None:
        reg = AgentRegistry()
        reg.register(FailingAgent(name="crasher", actions=["boom"]))
        dispatcher = AgentDispatcher(registry=reg)
        task = AgentTask(action="boom", agent_name="crasher")
        result = run(dispatcher.dispatch(task))
        assert not result.success
        assert "crashed" in (result.error or "").lower()

    def test_get_history(self, dispatcher: AgentDispatcher) -> None:
        run(dispatcher.dispatch(AgentTask(action="clerk-setup", task_id="h1")))
        run(dispatcher.dispatch(AgentTask(action="web-search", task_id="h2")))
        history = dispatcher.get_history()
        assert len(history) == 2

    def test_get_history_filtered(self, dispatcher: AgentDispatcher) -> None:
        run(dispatcher.dispatch(AgentTask(action="clerk-setup", task_id="f1")))
        run(dispatcher.dispatch(AgentTask(action="web-search", task_id="f2")))
        history = dispatcher.get_history(agent_name="devops")
        assert len(history) == 1
        assert history[0]["agent_name"] == "devops"

    def test_stats(self, dispatcher: AgentDispatcher) -> None:
        run(dispatcher.dispatch(AgentTask(action="clerk-setup", task_id="s1")))
        stats = dispatcher.get_stats()
        assert stats["total_dispatched"] == 1
        assert stats["completed"] == 1

    def test_get_lessons_empty(self, dispatcher: AgentDispatcher) -> None:
        run(dispatcher.dispatch(AgentTask(action="clerk-setup", task_id="l1")))
        lessons = dispatcher.get_lessons()
        assert lessons == []

    def test_get_lessons_after_failure(self) -> None:
        reg = AgentRegistry()
        reg.register(FailingAgent(name="bad", actions=["fail"]))
        dispatcher = AgentDispatcher(registry=reg)
        run(dispatcher.dispatch(AgentTask(action="fail", agent_name="bad", task_id="fail1")))
        lessons = dispatcher.get_lessons()
        assert len(lessons) == 1


# =========================================================================
# BrowserSessionPool
# =========================================================================

class TestBrowserSessionPool:
    """Test browser session pooling."""

    def test_initial_state(self) -> None:
        pool = BrowserSessionPool(max_sessions=3)
        assert pool.size == 0
        assert pool.available == 0
        assert pool.in_use == 0

    def test_initialize(self) -> None:
        pool = BrowserSessionPool()
        run(pool.initialize())
        assert pool.size == 0  # lazy creation — no sessions yet

    def test_acquire_before_init_raises(self) -> None:
        pool = BrowserSessionPool()
        with pytest.raises(RuntimeError, match="not initialized"):
            run(pool.acquire())

    def test_acquire_creates_session(self) -> None:
        pool = BrowserSessionPool(max_sessions=2)
        run(pool.initialize())

        mock_session = MagicMock()
        mock_session.start = AsyncMock()

        with patch("src.browser.session.BrowserSession", return_value=mock_session):
            session = run(pool.acquire())
            assert session is mock_session
            assert pool.size == 1
            assert pool.in_use == 1

    def test_release_makes_session_available(self) -> None:
        pool = BrowserSessionPool(max_sessions=2)
        run(pool.initialize())

        mock_session = MagicMock()
        mock_session.start = AsyncMock()

        with patch("src.browser.session.BrowserSession", return_value=mock_session):
            session = run(pool.acquire())
            assert pool.available == 0
            run(pool.release(session))
            assert pool.available == 1
            assert pool.in_use == 0

    def test_reuse_idle_session(self) -> None:
        pool = BrowserSessionPool(max_sessions=2)
        run(pool.initialize())

        mock_session = MagicMock()
        mock_session.start = AsyncMock()

        with patch("src.browser.session.BrowserSession", return_value=mock_session):
            s1 = run(pool.acquire())
            run(pool.release(s1))
            s2 = run(pool.acquire())
            assert s1 is s2  # same session reused
            assert pool.size == 1  # only one created

    def test_max_sessions_enforced(self) -> None:
        pool = BrowserSessionPool(max_sessions=1)
        run(pool.initialize())

        mock_session = MagicMock()
        mock_session.start = AsyncMock()

        with patch("src.browser.session.BrowserSession", return_value=mock_session):
            run(pool.acquire())  # takes the only slot
            with pytest.raises(RuntimeError, match="at capacity"):
                run(pool.acquire())

    def test_shutdown(self) -> None:
        pool = BrowserSessionPool(max_sessions=2)
        run(pool.initialize())

        mock_session = MagicMock()
        mock_session.start = AsyncMock()
        mock_session.close = AsyncMock()

        with patch("src.browser.session.BrowserSession", return_value=mock_session):
            run(pool.acquire())
            run(pool.shutdown())
            assert pool.size == 0
            mock_session.close.assert_called_once()

    def test_stats(self) -> None:
        pool = BrowserSessionPool(max_sessions=3)
        run(pool.initialize())

        mock_session = MagicMock()
        mock_session.start = AsyncMock()

        with patch("src.browser.session.BrowserSession", return_value=mock_session):
            run(pool.acquire())
            stats = pool.get_stats()
            assert stats["total_created"] == 1
            assert stats["total_acquired"] == 1
            assert stats["pool_size"] == 1
