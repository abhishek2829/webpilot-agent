"""WebPilot Agent — DevOps Setup Agent.

The first concrete agent in the multi-agent system. Wraps the existing
WebPilot workflow executor to provide DevOps automation:
  - Clerk auth setup
  - Vercel deployment
  - Supabase project creation
  - Stripe payments setup
  - GitHub repo creation
  - Domain/DNS configuration

This agent is designed to be registered with the AgentRegistry and
dispatched tasks by the AgentDispatcher (or a future Manager Agent).

Architecture position:
    Manager Agent
    └── DevOpsSetupAgent (THIS)
        ├── WorkflowRegistry (knows all YAML recipes)
        ├── WorkflowExecutor (runs the recipes)
        ├── BrowserSession (controls the browser)
        └── CheckpointManager (human-in-the-loop)
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.agents.base import (
    AgentCapability,
    AgentResult,
    AgentStatus,
    AgentTask,
)
from src.core.models import ExecutionStatus
from src.core.workflow_registry import WorkflowNotFoundError, WorkflowRegistry

logger = logging.getLogger(__name__)


# Map workflow names to the capabilities they provide
WORKFLOW_CAPABILITIES: dict[str, list[AgentCapability]] = {
    "clerk-setup": [
        AgentCapability.ACCOUNT_SETUP,
        AgentCapability.API_KEY_EXTRACTION,
        AgentCapability.BROWSER_AUTOMATION,
    ],
    "vercel-deploy": [
        AgentCapability.DEPLOYMENT,
        AgentCapability.BROWSER_AUTOMATION,
    ],
    "supabase-setup": [
        AgentCapability.ACCOUNT_SETUP,
        AgentCapability.API_KEY_EXTRACTION,
        AgentCapability.BROWSER_AUTOMATION,
    ],
    "stripe-setup": [
        AgentCapability.ACCOUNT_SETUP,
        AgentCapability.API_KEY_EXTRACTION,
        AgentCapability.WEBHOOK_CONFIGURATION,
        AgentCapability.BROWSER_AUTOMATION,
    ],
    "github-repo": [
        AgentCapability.REPOSITORY_MANAGEMENT,
        AgentCapability.BROWSER_AUTOMATION,
    ],
    "domain-setup": [
        AgentCapability.DNS_MANAGEMENT,
        AgentCapability.BROWSER_AUTOMATION,
    ],
}


class DevOpsSetupAgent:
    """DevOps setup agent — automates SaaS/infrastructure setup via browser.

    Implements the BaseAgent protocol. Wraps the WebPilot workflow executor
    to provide a multi-agent-compatible interface.

    Usage:
        agent = DevOpsSetupAgent(workflows_dir=Path("./workflows"))

        # Check what it can do
        print(agent.get_actions())
        print(agent.can_handle("clerk-setup"))

        # Execute a task
        task = AgentTask(action="clerk-setup", parameters={"project_name": "MyApp"})
        result = await agent.execute(task)
    """

    def __init__(
        self,
        workflows_dir: Path = Path("./workflows"),
    ) -> None:
        self._workflows_dir = workflows_dir
        self._registry = WorkflowRegistry(workflows_dir=workflows_dir)
        self._registry.load_all()
        self._status = AgentStatus.IDLE

        # Compound-engineering stats
        self._stats = {
            "total_tasks": 0,
            "completed": 0,
            "failed": 0,
        }
        self._task_log: list[dict[str, Any]] = []

    # =========================================================================
    # BaseAgent Protocol Implementation
    # =========================================================================

    @property
    def name(self) -> str:
        return "devops-setup"

    @property
    def description(self) -> str:
        return (
            "Automates DevOps and SaaS setup tasks via browser automation. "
            "Handles Clerk auth, Vercel deploys, Supabase projects, Stripe payments, "
            "GitHub repos, and domain/DNS configuration."
        )

    @property
    def capabilities(self) -> list[AgentCapability]:
        """Aggregate capabilities from all loaded workflows."""
        caps: set[AgentCapability] = set()
        for wf_name in self._registry.names:
            caps.update(WORKFLOW_CAPABILITIES.get(wf_name, []))
        # Always has these base capabilities
        caps.add(AgentCapability.BROWSER_AUTOMATION)
        caps.add(AgentCapability.FORM_FILLING)
        caps.add(AgentCapability.DATA_EXTRACTION)
        return sorted(caps, key=lambda c: c.value)

    @property
    def status(self) -> AgentStatus:
        return self._status

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute a DevOps setup task.

        The task.action must match a workflow name in the registry
        (e.g., 'clerk-setup', 'vercel-deploy').

        Args:
            task: AgentTask with action (workflow name) and parameters (variables)

        Returns:
            AgentResult with extracted data (API keys, URLs, etc.)
        """
        task_id = task.task_id or f"devops-{uuid4().hex[:12]}"
        start_time = time.monotonic()
        self._status = AgentStatus.BUSY
        self._stats["total_tasks"] += 1

        logger.info(
            "DevOpsSetupAgent executing task",
            extra={
                "task_id": task_id,
                "action": task.action,
                "parameters": list(task.parameters.keys()),
            },
        )

        try:
            # Validate the action maps to a workflow
            workflow = self._registry.get(task.action)

            # Import execution components (deferred to avoid circular imports
            # and to keep the agent lightweight until execution)
            from src.browser.actions import ActionEngine
            from src.browser.session import BrowserSession
            from src.checkpoints.manager import CheckpointManager
            from src.core.executor import WorkflowExecutor
            from src.core.recovery import RecoveryEngine

            # Wire up the execution pipeline
            checkpoint_mgr = CheckpointManager(
                mode=task.checkpoint_mode,
                timeout_seconds=300,
            )

            # LLM brain is optional — only loaded if API key is available
            llm_brain = None
            try:
                import os
                api_key = os.environ.get("ANTHROPIC_API_KEY", "")
                if api_key:
                    from src.core.llm_brain import LLMBrain
                    llm_brain = LLMBrain(api_key=api_key)
            except Exception:
                pass

            action_engine = ActionEngine(llm_brain=llm_brain)
            recovery_engine = RecoveryEngine(
                action_engine=action_engine,
                llm_brain=llm_brain,
                checkpoint_manager=checkpoint_mgr,
            )
            executor = WorkflowExecutor(
                action_engine=action_engine,
                checkpoint_manager=checkpoint_mgr,
                recovery_engine=recovery_engine,
            )

            # Create browser session and execute
            session = BrowserSession(headless=task.headless)
            try:
                await session.start()
                result = await executor.execute(
                    workflow=workflow,
                    session=session,
                    variables=task.parameters,
                )
            finally:
                await session.close()

            duration_ms = int((time.monotonic() - start_time) * 1000)

            if result.status == ExecutionStatus.COMPLETED:
                self._stats["completed"] += 1
                self._status = AgentStatus.IDLE
                agent_result = AgentResult(
                    task_id=task_id,
                    agent_name=self.name,
                    success=True,
                    data={
                        "execution_id": result.id,
                        "workflow_name": result.workflow_name,
                        "extracted_variables": result.extracted_variables,
                        "steps_completed": len(result.step_results),
                    },
                    duration_ms=duration_ms,
                )
            else:
                self._stats["failed"] += 1
                self._status = AgentStatus.IDLE
                agent_result = AgentResult(
                    task_id=task_id,
                    agent_name=self.name,
                    success=False,
                    data={
                        "execution_id": result.id,
                        "workflow_name": result.workflow_name,
                        "status": result.status.value,
                    },
                    error=result.error,
                    duration_ms=duration_ms,
                )

        except WorkflowNotFoundError as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            self._stats["failed"] += 1
            self._status = AgentStatus.IDLE
            agent_result = AgentResult(
                task_id=task_id,
                agent_name=self.name,
                success=False,
                error=f"Unknown action: {task.action}. {e}",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            self._stats["failed"] += 1
            self._status = AgentStatus.ERROR
            agent_result = AgentResult(
                task_id=task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

        self._log_task(task, agent_result)
        return agent_result

    def can_handle(self, action: str) -> bool:
        """Check if this agent can handle a given action (workflow name)."""
        return self._registry.exists(action)

    def get_actions(self) -> list[dict[str, str]]:
        """List all workflows this agent can execute."""
        return [
            {"name": wf["name"], "description": wf["description"]}
            for wf in self._registry.list_workflows()
        ]

    def get_stats(self) -> dict[str, int]:
        """Return task execution statistics."""
        return dict(self._stats)

    # =========================================================================
    # Compound Engineering — Task Logging
    # =========================================================================

    def get_lessons(self) -> list[dict[str, Any]]:
        """Return lessons from failed tasks."""
        return [
            entry for entry in self._task_log
            if not entry.get("success", True)
        ]

    def _log_task(self, task: AgentTask, result: AgentResult) -> None:
        """Log task execution for observability."""
        self._task_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_id": result.task_id,
            "action": task.action,
            "success": result.success,
            "duration_ms": result.duration_ms,
            "error": result.error,
        })
