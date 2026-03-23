"""WebPilot Agent — Finance Agent.

Automates finance/accounting workflows via browser automation:
  - Invoice tracking (Stripe, PayPal dashboard monitoring)
  - Payment monitoring (check payment statuses)
  - Expense report extraction (bank/card statements)
  - Subscription audit (find and catalog active subscriptions)
  - Revenue dashboard extraction (Stripe, Paddle metrics)
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.agents.base import AgentCapability, AgentResult, AgentStatus, AgentTask
from src.core.workflow_registry import WorkflowNotFoundError, WorkflowRegistry

logger = logging.getLogger(__name__)


class FinanceAgent:
    """Finance agent — automates invoice, payment, and subscription workflows."""

    def __init__(self, workflows_dir: Path = Path("./workflows/finance")) -> None:
        self._workflows_dir = workflows_dir
        self._registry = WorkflowRegistry(workflows_dir=workflows_dir)
        self._registry.load_all()
        self._status = AgentStatus.IDLE
        self._stats = {"total_tasks": 0, "completed": 0, "failed": 0}
        self._task_log: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "finance"

    @property
    def description(self) -> str:
        return (
            "Automates finance operations — invoice tracking, payment monitoring, "
            "expense reports, subscription audits, and revenue dashboard extraction."
        )

    @property
    def capabilities(self) -> list[AgentCapability]:
        return sorted([AgentCapability.BROWSER_AUTOMATION, AgentCapability.DATA_EXTRACTION], key=lambda c: c.value)

    @property
    def status(self) -> AgentStatus:
        return self._status

    async def execute(self, task: AgentTask) -> AgentResult:
        task_id = task.task_id or f"finance-{uuid4().hex[:12]}"
        start_time = time.monotonic()
        self._status = AgentStatus.BUSY
        self._stats["total_tasks"] += 1

        try:
            workflow = self._registry.get(task.action)
            from src.browser.actions import ActionEngine
            from src.browser.session import BrowserSession
            from src.checkpoints.manager import CheckpointManager
            from src.core.executor import WorkflowExecutor
            from src.core.recovery import RecoveryEngine

            checkpoint_mgr = CheckpointManager(mode=task.checkpoint_mode, timeout_seconds=300)
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
            recovery_engine = RecoveryEngine(action_engine=action_engine, llm_brain=llm_brain, checkpoint_manager=checkpoint_mgr)
            executor = WorkflowExecutor(action_engine=action_engine, checkpoint_manager=checkpoint_mgr, recovery_engine=recovery_engine)

            session = BrowserSession(headless=task.headless)
            try:
                await session.start()
                result = await executor.execute(workflow=workflow, session=session, variables=task.parameters)
            finally:
                await session.close()

            duration_ms = int((time.monotonic() - start_time) * 1000)
            from src.core.models import ExecutionStatus
            success = result.status == ExecutionStatus.COMPLETED
            if success:
                self._stats["completed"] += 1
            else:
                self._stats["failed"] += 1
            self._status = AgentStatus.IDLE
            return AgentResult(task_id=task_id, agent_name=self.name, success=success, data={"execution_id": result.id, "extracted_variables": result.extracted_variables} if success else {"status": result.status.value}, error=result.error if not success else None, duration_ms=duration_ms)

        except WorkflowNotFoundError as e:
            self._stats["failed"] += 1
            self._status = AgentStatus.IDLE
            return AgentResult(task_id=task_id, agent_name=self.name, success=False, error=f"Unknown action: {task.action}. {e}", duration_ms=int((time.monotonic() - start_time) * 1000))
        except Exception as e:
            self._stats["failed"] += 1
            self._status = AgentStatus.ERROR
            return AgentResult(task_id=task_id, agent_name=self.name, success=False, error=str(e), duration_ms=int((time.monotonic() - start_time) * 1000))

    def can_handle(self, action: str) -> bool:
        return self._registry.exists(action)

    def get_actions(self) -> list[dict[str, str]]:
        return [{"name": wf["name"], "description": wf["description"]} for wf in self._registry.list_workflows()]

    def get_stats(self) -> dict[str, int]:
        return dict(self._stats)

    def get_lessons(self) -> list[dict[str, Any]]:
        return [e for e in self._task_log if not e.get("success", True)]
