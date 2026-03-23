"""WebPilot Agent — Agent Dispatcher.

Routes tasks to the right agent, manages execution lifecycle, and
stores results for retrieval. This is the control plane for the
multi-agent system.

Usage:
    dispatcher = AgentDispatcher(agent_registry)

    # Dispatch a task (finds the right agent automatically)
    result = await dispatcher.dispatch(AgentTask(action="clerk-setup", ...))

    # Or dispatch to a specific agent
    result = await dispatcher.dispatch_to("devops-setup", AgentTask(...))

    # Check execution history
    history = dispatcher.get_history(limit=10)

The dispatcher also acts as the execution store — it tracks all
task results in memory (with PostgreSQL persistence coming via
the existing Database class).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.agents.base import (
    AgentRegistry,
    AgentResult,
    AgentStatus,
    AgentTask,
)

logger = logging.getLogger(__name__)


class DispatchError(Exception):
    """Raised when task dispatch fails."""
    pass


class AgentDispatcher:
    """Routes tasks to agents, tracks execution results.

    The dispatcher is the single entry point for submitting work
    to the multi-agent system. It:
      1. Resolves which agent should handle the task
      2. Validates the agent is available
      3. Executes the task
      4. Stores the result for retrieval
    """

    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry
        self._results: dict[str, AgentResult] = {}
        self._pending: dict[str, AgentTask] = {}
        self._stats = {
            "total_dispatched": 0,
            "completed": 0,
            "failed": 0,
            "no_agent_found": 0,
        }

    # =========================================================================
    # Dispatch
    # =========================================================================

    async def dispatch(self, task: AgentTask) -> AgentResult:
        """Dispatch a task to the appropriate agent.

        Finds the right agent by matching task.action against registered
        agents' can_handle() method. If task.agent_name is set, dispatches
        directly to that agent.

        Args:
            task: The task to execute

        Returns:
            AgentResult from the executing agent

        Raises:
            DispatchError: If no agent can handle the task
        """
        # Assign task ID if not set
        if not task.task_id:
            task.task_id = f"task-{uuid4().hex[:12]}"

        # Route to specific agent if requested
        if task.agent_name:
            return await self.dispatch_to(task.agent_name, task)

        # Find an agent that can handle this action
        agent = self._registry.find_for_action(task.action)
        if not agent:
            self._stats["no_agent_found"] += 1
            raise DispatchError(
                f"No agent can handle action '{task.action}'. "
                f"Available agents: {', '.join(self._registry.names) or '(none)'}"
            )

        task.agent_name = agent.name
        return await self._execute(task)

    async def dispatch_to(self, agent_name: str, task: AgentTask) -> AgentResult:
        """Dispatch a task to a specific agent by name.

        Args:
            agent_name: Name of the target agent
            task: The task to execute

        Returns:
            AgentResult from the executing agent

        Raises:
            DispatchError: If the agent is not found or unavailable
        """
        if not task.task_id:
            task.task_id = f"task-{uuid4().hex[:12]}"

        try:
            agent = self._registry.get(agent_name)
        except KeyError as e:
            self._stats["no_agent_found"] += 1
            raise DispatchError(str(e)) from e

        task.agent_name = agent_name
        return await self._execute(task)

    async def _execute(self, task: AgentTask) -> AgentResult:
        """Internal: execute a task on the resolved agent."""
        self._stats["total_dispatched"] += 1
        self._pending[task.task_id] = task

        agent = self._registry.get(task.agent_name)

        # Check agent availability
        if agent.status == AgentStatus.OFFLINE:
            self._stats["failed"] += 1
            result = AgentResult(
                task_id=task.task_id,
                agent_name=task.agent_name,
                success=False,
                error=f"Agent '{task.agent_name}' is offline",
            )
            self._results[task.task_id] = result
            self._pending.pop(task.task_id, None)
            return result

        logger.info(
            "Dispatching task",
            extra={
                "task_id": task.task_id,
                "agent_name": task.agent_name,
                "action": task.action,
            },
        )

        try:
            result = await agent.execute(task)
        except Exception as e:
            logger.error(
                "Task execution failed",
                extra={
                    "task_id": task.task_id,
                    "agent_name": task.agent_name,
                    "error": str(e),
                },
            )
            result = AgentResult(
                task_id=task.task_id,
                agent_name=task.agent_name,
                success=False,
                error=str(e),
            )

        # Store result and update stats
        self._results[task.task_id] = result
        self._pending.pop(task.task_id, None)

        if result.success:
            self._stats["completed"] += 1
        else:
            self._stats["failed"] += 1

        logger.info(
            "Task completed",
            extra={
                "task_id": task.task_id,
                "agent_name": task.agent_name,
                "success": result.success,
                "duration_ms": result.duration_ms,
            },
        )

        return result

    # =========================================================================
    # Result Retrieval
    # =========================================================================

    def get_result(self, task_id: str) -> AgentResult | None:
        """Get the result of a completed task."""
        return self._results.get(task_id)

    def get_pending(self, task_id: str) -> AgentTask | None:
        """Get a pending (in-progress) task."""
        return self._pending.get(task_id)

    def is_pending(self, task_id: str) -> bool:
        """Check if a task is still in progress."""
        return task_id in self._pending

    def get_history(
        self,
        agent_name: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get execution history, most recent first.

        Args:
            agent_name: Filter by agent (optional)
            limit: Maximum results to return
        """
        results = list(self._results.values())

        if agent_name:
            results = [r for r in results if r.agent_name == agent_name]

        # Sort by completion time descending
        results.sort(key=lambda r: r.completed_at, reverse=True)

        return [r.to_dict() for r in results[:limit]]

    # =========================================================================
    # Stats
    # =========================================================================

    def get_stats(self) -> dict[str, int]:
        """Return dispatch statistics."""
        return {
            **self._stats,
            "pending": len(self._pending),
            "results_stored": len(self._results),
        }

    def get_lessons(self) -> list[dict[str, Any]]:
        """Return failed dispatches as lessons."""
        return [
            r.to_dict() for r in self._results.values()
            if not r.success
        ]
