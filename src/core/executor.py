"""WebPilot Agent — Workflow Executor.

The central loop — the heartbeat of the agent. Reads a workflow (the score),
iterates through steps, and orchestrates the browser engine, checkpoint
manager, and recovery engine to execute each step.

Analogy: An orchestra conductor. The instruments (browser, LLM, checkpoints)
are all warmed up. The conductor reads the score (workflow YAML), cues each
instrument in turn, handles mistakes (recovery), and knows when to ask
the audience (human) for permission to continue (checkpoints).

Patterns applied:
- gsd-checkpoint-protocol: delegates to CheckpointManager for human approvals
- gsd-verification-patterns: validates each step result before moving on
- compound-engineering: every execution logged with timing, errors, outcomes
- autoresearch: track which workflows/steps succeed/fail for improvement
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from src.browser.actions import ActionError, ActionResult
from src.core.models import (
    ExecutionResult,
    ExecutionStatus,
    Step,
    StepResult,
    StepType,
    Workflow,
)
from src.core.recovery import RecoveryResult

logger = logging.getLogger(__name__)


class ExecutorError(Exception):
    """Raised for executor-level failures (not step-level)."""
    pass


class WorkflowExecutor:
    """Executes a workflow step by step, orchestrating all components.

    The executor is the integration point between:
      - ActionEngine: executes browser steps (click, type, navigate, etc.)
      - CheckpointManager: handles human approval steps
      - RecoveryEngine: recovers from step failures

    Usage:
        executor = WorkflowExecutor(
            action_engine=engine,
            checkpoint_manager=checkpoint_mgr,
            recovery_engine=recovery_eng,
        )
        result = await executor.execute(workflow, session, variables={"project_name": "MyApp"})

    Thread safety: One executor can run multiple workflows sequentially.
    Don't run concurrent executions on the same executor.
    """

    def __init__(
        self,
        action_engine: Any,
        checkpoint_manager: Any,
        recovery_engine: Any,
    ) -> None:
        self._action_engine = action_engine
        self._checkpoint_manager = checkpoint_manager
        self._recovery_engine = recovery_engine

        # Compound-engineering: track execution stats
        self._operation_log: list[dict[str, Any]] = []
        self._stats = {
            "total_executions": 0,
            "completed": 0,
            "failed": 0,
            "aborted": 0,
        }

    # =========================================================================
    # Main Entry Point
    # =========================================================================

    async def execute(
        self,
        workflow: Workflow,
        session: Any,
        variables: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """Execute a workflow step by step.

        Args:
            workflow: The Workflow to execute
            session: A BrowserSession (already started)
            variables: User-provided variables to override workflow defaults

        Returns:
            ExecutionResult with status, step results, extracted variables, timing
        """
        started_at = datetime.now(timezone.utc)
        start_time = time.monotonic()
        self._stats["total_executions"] += 1

        # Resolve variable placeholders in all steps
        resolved_steps = workflow.resolved_steps(variables)
        extracted_variables: dict[str, str] = {}
        step_results: list[StepResult] = []

        # Build the execution result (will be updated as we go)
        result = ExecutionResult(
            workflow_name=workflow.name,
            status=ExecutionStatus.RUNNING,
            started_at=started_at,
        )

        logger.info(
            "Starting workflow execution",
            extra={
                "workflow": workflow.name,
                "total_steps": len(resolved_steps),
                "execution_id": result.id,
            },
        )

        for i, step in enumerate(resolved_steps):
            step_start = time.monotonic()

            try:
                if step.type == StepType.CHECKPOINT:
                    # ── Checkpoint: ask human for approval ──
                    step_result = await self._handle_checkpoint(
                        step=step,
                        session=session,
                        context={
                            "execution_id": result.id,
                            "step_index": i,
                            "variables": {**(variables or {}), **extracted_variables},
                        },
                    )

                    if step_result.status == "aborted":
                        result.status = ExecutionStatus.ABORTED
                        result.error = f"User rejected checkpoint at step {i}"
                        step_results.append(step_result)
                        break
                else:
                    # ── Browser action: execute via action engine ──
                    step_result = await self._handle_action(
                        step=step,
                        step_index=i,
                        session=session,
                        extracted_variables=extracted_variables,
                        execution_id=result.id,
                    )

                    if step_result.status == "failed":
                        result.status = ExecutionStatus.FAILED
                        result.error = step_result.error
                        step_results.append(step_result)
                        break

                step_result.duration_ms = int((time.monotonic() - step_start) * 1000)
                step_results.append(step_result)

            except Exception as e:
                logger.error(
                    "Unexpected error during execution",
                    extra={"step_index": i, "error": str(e)},
                )
                step_results.append(
                    StepResult(
                        step_index=i,
                        step_type=step.type,
                        status="failed",
                        error=str(e),
                    )
                )
                result.status = ExecutionStatus.FAILED
                result.error = str(e)
                break
        else:
            # All steps completed successfully
            result.status = ExecutionStatus.COMPLETED

        # Finalize result
        result.step_results = step_results
        result.extracted_variables = extracted_variables
        result.completed_at = datetime.now(timezone.utc)
        result.total_duration_ms = int((time.monotonic() - start_time) * 1000)

        # Update stats
        if result.status == ExecutionStatus.COMPLETED:
            self._stats["completed"] += 1
        elif result.status == ExecutionStatus.FAILED:
            self._stats["failed"] += 1
        elif result.status == ExecutionStatus.ABORTED:
            self._stats["aborted"] += 1

        # Log for compound-engineering
        self._log_execution(result)

        logger.info(
            "Workflow execution finished",
            extra={
                "workflow": workflow.name,
                "status": result.status.value,
                "duration_ms": result.total_duration_ms,
                "steps_completed": len(step_results),
                "extracted_variables": list(extracted_variables.keys()),
            },
        )

        return result

    # =========================================================================
    # Step Handlers
    # =========================================================================

    async def _handle_checkpoint(
        self,
        step: Step,
        session: Any,
        context: dict[str, Any],
    ) -> StepResult:
        """Handle a checkpoint step: screenshot + human approval."""
        # Take screenshot if the step requests it
        screenshot = None
        screenshot_path = None
        if step.screenshot:
            try:
                screenshot = await session.screenshot()
            except Exception as e:
                logger.warning(f"Failed to take screenshot for checkpoint: {e}")

        checkpoint_result = await self._checkpoint_manager.request_approval(
            step=step,
            screenshot=screenshot,
            context=context,
        )

        if checkpoint_result.approved:
            return StepResult(
                step_index=context["step_index"],
                step_type=StepType.CHECKPOINT,
                status="success",
                data={
                    "approved": True,
                    "by": checkpoint_result.by,
                },
            )
        else:
            return StepResult(
                step_index=context["step_index"],
                step_type=StepType.CHECKPOINT,
                status="aborted",
                data={
                    "approved": False,
                    "by": checkpoint_result.by,
                    "reason": checkpoint_result.reason,
                },
            )

    async def _handle_action(
        self,
        step: Step,
        step_index: int,
        session: Any,
        extracted_variables: dict[str, str],
        execution_id: str,
    ) -> StepResult:
        """Handle a browser action step with recovery on failure."""
        page = session.page

        try:
            action_result: ActionResult = await self._action_engine.execute(page, step)

            # Store extracted values
            if step.type == StepType.EXTRACT and step.variable and action_result.extracted_value:
                extracted_variables[step.variable] = action_result.extracted_value

            return StepResult(
                step_index=step_index,
                step_type=step.type,
                status="success",
                data={
                    "strategy_used": action_result.strategy_used,
                    "extracted_value": action_result.extracted_value,
                },
            )

        except ActionError as e:
            # Delegate to recovery engine
            logger.warning(
                "Step failed, attempting recovery",
                extra={"step_index": step_index, "error": str(e)},
            )

            recovery_result: RecoveryResult = await self._recovery_engine.handle(
                page=page,
                step=step,
                error=e,
                context={
                    "step_index": step_index,
                    "execution_id": execution_id,
                },
            )

            if recovery_result.resolved:
                # Recovery succeeded — check if we got an extraction result
                if (
                    recovery_result.action_result
                    and step.type == StepType.EXTRACT
                    and step.variable
                    and recovery_result.action_result.extracted_value
                ):
                    extracted_variables[step.variable] = recovery_result.action_result.extracted_value

                return StepResult(
                    step_index=step_index,
                    step_type=step.type,
                    status="success",
                    data={
                        "recovered": True,
                        "recovery_strategy": recovery_result.strategy_used,
                    },
                )
            else:
                return StepResult(
                    step_index=step_index,
                    step_type=step.type,
                    status="failed",
                    error=recovery_result.error or str(e),
                )

    # =========================================================================
    # Compound Engineering — Logging & Lessons
    # =========================================================================

    def get_stats(self) -> dict[str, int]:
        """Return execution statistics."""
        return dict(self._stats)

    def get_lessons(self) -> list[dict[str, Any]]:
        """Return lessons from failed/aborted executions.

        Following compound-engineering pattern: failures become lessons
        that improve future workflow definitions and recovery strategies.
        """
        return [
            op for op in self._operation_log
            if op.get("status") in ("failed", "aborted")
        ]

    def _log_execution(self, result: ExecutionResult) -> None:
        """Log an execution for compound-engineering analysis."""
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": result.id,
            "workflow_name": result.workflow_name,
            "status": result.status.value,
            "total_steps": len(result.step_results),
            "duration_ms": result.total_duration_ms,
            "extracted_variables": list(result.extracted_variables.keys()),
        }

        if result.error:
            entry["error"] = result.error

        self._operation_log.append(entry)

        logger.debug("Execution logged", extra=entry)
