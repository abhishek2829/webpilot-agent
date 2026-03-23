"""WebPilot Agent — Base Agent Protocol & Registry.

Defines the contract that all agents in the multi-agent system must follow,
and the registry that discovers, validates, and serves agent instances.

Architecture:
    Manager Agent (future orchestrator)
    ├── DevOpsSetupAgent (THIS PROJECT)
    ├── ResearchAgent (future)
    ├── SalesAgent (future)
    └── FinanceAgent (future)

Each agent:
  - Has a name, description, and list of capabilities
  - Can accept tasks and return results
  - Shares infrastructure: browser sessions, credential vault, checkpoint system
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# =========================================================================
# Agent Capability — What an agent can do
# =========================================================================

class AgentCapability(str, Enum):
    """Capabilities that agents can declare."""
    BROWSER_AUTOMATION = "browser_automation"
    DATA_EXTRACTION = "data_extraction"
    FORM_FILLING = "form_filling"
    ACCOUNT_SETUP = "account_setup"
    DEPLOYMENT = "deployment"
    DNS_MANAGEMENT = "dns_management"
    API_KEY_EXTRACTION = "api_key_extraction"
    WEBHOOK_CONFIGURATION = "webhook_configuration"
    REPOSITORY_MANAGEMENT = "repository_management"


class AgentStatus(str, Enum):
    """Current status of an agent."""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


# =========================================================================
# Agent Task — Input/output for agent work
# =========================================================================

@dataclass
class AgentTask:
    """A task submitted to an agent for execution.

    Attributes:
        task_id: Unique identifier (auto-generated if empty)
        agent_name: Target agent name (resolved by dispatcher)
        action: What to do (e.g., "clerk-setup", "vercel-deploy")
        parameters: Action-specific parameters
        checkpoint_mode: How to handle human approvals
        headless: Whether to run browser in headless mode
        submitted_by: Who submitted this task
    """
    action: str
    parameters: dict[str, str] = field(default_factory=dict)
    task_id: str = ""
    agent_name: str = ""
    checkpoint_mode: str = "auto"
    headless: bool = True
    submitted_by: str = "system"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AgentResult:
    """Result returned by an agent after executing a task.

    Attributes:
        task_id: The original task ID
        agent_name: Which agent handled it
        success: Whether the task completed successfully
        data: Extracted data / results
        error: Error message if failed
        duration_ms: How long the task took
    """
    task_id: str
    agent_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: int = 0
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API responses."""
        result: dict[str, Any] = {
            "task_id": self.task_id,
            "agent_name": self.agent_name,
            "success": self.success,
            "data": self.data,
            "duration_ms": self.duration_ms,
            "completed_at": self.completed_at.isoformat(),
        }
        if self.error:
            result["error"] = self.error
        return result


# =========================================================================
# Base Agent Protocol — The contract all agents must follow
# =========================================================================

@runtime_checkable
class BaseAgent(Protocol):
    """Protocol defining what every agent in the system must implement.

    Any class implementing these methods can be registered as an agent.
    This is a structural subtype (Protocol) — no inheritance required.
    """

    @property
    def name(self) -> str:
        """Unique agent identifier (e.g., 'devops-setup')."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description of what the agent does."""
        ...

    @property
    def capabilities(self) -> list[AgentCapability]:
        """List of capabilities this agent provides."""
        ...

    @property
    def status(self) -> AgentStatus:
        """Current agent status."""
        ...

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute a task and return the result.

        Args:
            task: The task to execute

        Returns:
            AgentResult with success/failure status and extracted data
        """
        ...

    def can_handle(self, action: str) -> bool:
        """Check if this agent can handle a given action.

        Args:
            action: The action identifier (e.g., 'clerk-setup')

        Returns:
            True if this agent knows how to perform the action
        """
        ...

    def get_actions(self) -> list[dict[str, str]]:
        """List all actions this agent can perform.

        Returns:
            List of dicts with 'name' and 'description' keys
        """
        ...

    def get_stats(self) -> dict[str, int]:
        """Return operational statistics (compound-engineering pattern)."""
        ...


# =========================================================================
# Agent Registry — Discovers and manages agents
# =========================================================================

class AgentRegistry:
    """Registry for discovering and managing agent instances.

    Usage:
        registry = AgentRegistry()
        registry.register(devops_agent)
        registry.register(research_agent)

        agent = registry.get("devops-setup")
        agents = registry.find_by_capability(AgentCapability.BROWSER_AUTOMATION)
        agent = registry.find_for_action("clerk-setup")
    """

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}
        self._registration_log: list[dict[str, Any]] = []

    def register(self, agent: BaseAgent) -> None:
        """Register an agent with the registry.

        Args:
            agent: An object implementing the BaseAgent protocol

        Raises:
            TypeError: If the agent doesn't implement the protocol
            ValueError: If an agent with the same name is already registered
        """
        if not isinstance(agent, BaseAgent):
            raise TypeError(
                f"Agent must implement BaseAgent protocol, got {type(agent).__name__}"
            )

        if agent.name in self._agents:
            raise ValueError(f"Agent '{agent.name}' is already registered")

        self._agents[agent.name] = agent
        self._registration_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_name": agent.name,
            "capabilities": [c.value for c in agent.capabilities],
            "actions": len(agent.get_actions()),
        })

        logger.info(
            "Agent registered",
            extra={"agent_name": agent.name, "capabilities": len(agent.capabilities)},
        )

    def unregister(self, name: str) -> None:
        """Remove an agent from the registry."""
        self._agents.pop(name, None)

    def get(self, name: str) -> BaseAgent:
        """Get an agent by name.

        Raises:
            KeyError: If the agent is not registered
        """
        if name not in self._agents:
            available = ", ".join(sorted(self._agents.keys())) or "(none)"
            raise KeyError(f"Agent '{name}' not found. Available: {available}")
        return self._agents[name]

    def exists(self, name: str) -> bool:
        """Check if an agent is registered."""
        return name in self._agents

    def list_agents(self) -> list[dict[str, Any]]:
        """List all registered agents with metadata."""
        return [
            {
                "name": agent.name,
                "description": agent.description,
                "status": agent.status.value,
                "capabilities": [c.value for c in agent.capabilities],
                "actions": agent.get_actions(),
            }
            for agent in sorted(self._agents.values(), key=lambda a: a.name)
        ]

    def find_by_capability(self, capability: AgentCapability) -> list[BaseAgent]:
        """Find all agents that have a specific capability."""
        return [
            agent for agent in self._agents.values()
            if capability in agent.capabilities
        ]

    def find_for_action(self, action: str) -> BaseAgent | None:
        """Find the first agent that can handle a given action.

        Returns None if no agent can handle it.
        """
        for agent in self._agents.values():
            if agent.can_handle(action):
                return agent
        return None

    @property
    def count(self) -> int:
        """Number of registered agents."""
        return len(self._agents)

    @property
    def names(self) -> list[str]:
        """Sorted list of registered agent names."""
        return sorted(self._agents.keys())

    def get_registration_log(self) -> list[dict[str, Any]]:
        """Full registration history."""
        return list(self._registration_log)
