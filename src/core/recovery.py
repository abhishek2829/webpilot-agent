"""WebPilot Agent — Recovery Engine.

Three-tier recovery strategy for handling failures during workflow execution:
  Tier 1: Retry — same action, fresh attempt (handles transient failures)
  Tier 2: LLM Adapt — ask Claude to find a new selector (handles UI changes)
  Tier 3: Escalate — show the user and ask for help (last resort)

Analogy: A pilot's emergency checklist:
  - Engine sputter? → Try restarting (retry)
  - Engine dead? → Ask copilot for alternatives (LLM adapt)
  - Nothing works? → Radio the tower (escalate to human)

Patterns applied:
- gsd-checkpoint-protocol: escalation to human checkpoint as last resort
- compound-engineering: every recovery attempt logged for lessons
- autoresearch: track which recovery strategies work for which error types
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from playwright.async_api import Page

from src.browser.actions import ActionError, ActionResult, ElementNotFoundError
from src.core.models import (
    CheckpointResult,
    FallbackStrategy,
    Step,
    StepType,
)

logger = logging.getLogger(__name__)


@dataclass
class RecoveryResult:
    """Outcome of a recovery attempt."""
    resolved: bool
    strategy_used: str  # "retry", "llm_adapt", "escalate", "skip", "fail", "exhausted"
    action_result: ActionResult | None = None
    error: str | None = None


class RecoveryEngine:
    """Three-tier recovery for workflow step failures.

    When a step fails during execution, the recovery engine attempts
    to resolve it using progressively more expensive strategies:

    1. Retry: Re-execute the same step (fast, handles transient issues)
    2. LLM Adapt: Screenshot the page, ask Claude for a new selector
       (only for steps with fallback_strategy=llm_vision)
    3. Escalate: Create a checkpoint, show the user the failure,
       and ask them to fix it manually or abort

    Usage:
        recovery = RecoveryEngine(action_engine, llm_brain, checkpoint_manager)
        result = await recovery.handle(page, step, error, context)
        if result.resolved:
            # continue
        else:
            # fail the workflow

    Thread safety: One engine per execution. Don't share across concurrent workflows.
    """

    def __init__(
        self,
        action_engine: Any,
        llm_brain: Any | None = None,
        checkpoint_manager: Any | None = None,
    ) -> None:
        self._action_engine = action_engine
        self._llm_brain = llm_brain
        self._checkpoint_manager = checkpoint_manager

        # Compound-engineering: log every recovery attempt
        self._operation_log: list[dict[str, Any]] = []
        self._stats = {
            "total_recoveries": 0,
            "retry_success": 0,
            "llm_adapt_success": 0,
            "escalate_success": 0,
            "skip_count": 0,
            "fail_count": 0,
            "unresolved": 0,
        }

    # =========================================================================
    # Main Entry Point
    # =========================================================================

    async def handle(
        self,
        page: Page,
        step: Step,
        error: Exception,
        context: dict[str, Any] | None = None,
    ) -> RecoveryResult:
        """Attempt to recover from a step failure.

        Walks through the three tiers in order, stopping as soon as
        one succeeds. Respects the step's fallback_strategy setting.

        Args:
            page: The Playwright page (for retries and screenshots)
            step: The Step that failed
            error: The exception that was raised
            context: Execution context (step_index, execution_id, etc.)

        Returns:
            RecoveryResult indicating whether the issue was resolved
        """
        ctx = context or {}
        self._stats["total_recoveries"] += 1

        logger.warning(
            "Recovery triggered",
            extra={
                "step_index": ctx.get("step_index"),
                "step_type": step.type.value,
                "error": str(error),
                "fallback_strategy": step.fallback_strategy.value,
            },
        )

        # ── Fail-fast: step explicitly says "don't try to recover" ──
        if step.fallback_strategy == FallbackStrategy.FAIL:
            result = RecoveryResult(
                resolved=False,
                strategy_used="fail",
                error=str(error),
            )
            self._stats["fail_count"] += 1
            self._log_operation(step, "fail", resolved=False, error=str(error), context=ctx)
            return result

        # ── Skip: optional step, just move on ──
        if step.fallback_strategy == FallbackStrategy.SKIP:
            result = RecoveryResult(
                resolved=True,
                strategy_used="skip",
            )
            self._stats["skip_count"] += 1
            self._log_operation(step, "skip", resolved=True, context=ctx)
            return result

        # ── Tier 1: Retry ──
        retry_result = await self._try_retry(page, step, ctx)
        if retry_result and retry_result.resolved:
            return retry_result

        # ── Tier 2: LLM Adapt (only for llm_vision fallback strategy) ──
        if (
            step.fallback_strategy == FallbackStrategy.LLM_VISION
            and self._llm_brain is not None
        ):
            adapt_result = await self._try_llm_adapt(page, step, error, ctx)
            if adapt_result and adapt_result.resolved:
                return adapt_result

        # ── Tier 3: Escalate to human checkpoint ──
        if self._checkpoint_manager is not None:
            escalate_result = await self._try_escalate(page, step, error, ctx)
            return escalate_result

        # ── All strategies exhausted ──
        result = RecoveryResult(
            resolved=False,
            strategy_used="exhausted",
            error=f"All recovery strategies failed for step: {str(error)}",
        )
        self._stats["unresolved"] += 1
        self._log_operation(step, "exhausted", resolved=False, error=str(error), context=ctx)
        return result

    # =========================================================================
    # Tier 1: Retry
    # =========================================================================

    async def _try_retry(
        self,
        page: Page,
        step: Step,
        context: dict[str, Any],
    ) -> RecoveryResult | None:
        """Tier 1: Retry the same action.

        Simple retry — the step's original max_retries may have already
        been exhausted by the ActionEngine, so this is one additional
        "recovery retry" with a clean slate.
        """
        try:
            action_result = await self._action_engine.execute(page, step)
            if action_result.success:
                self._stats["retry_success"] += 1
                self._log_operation(step, "retry", resolved=True, context=context)
                return RecoveryResult(
                    resolved=True,
                    strategy_used="retry",
                    action_result=action_result,
                )
        except Exception as e:
            logger.debug(
                "Retry failed",
                extra={"error": str(e), "step_index": context.get("step_index")},
            )

        return None

    # =========================================================================
    # Tier 2: LLM Adapt
    # =========================================================================

    async def _try_llm_adapt(
        self,
        page: Page,
        step: Step,
        original_error: Exception,
        context: dict[str, Any],
    ) -> RecoveryResult | None:
        """Tier 2: Ask the LLM to find a new selector.

        Takes a screenshot, sends it to Claude with the step description,
        and asks for a CSS selector that matches the target element.
        Then retries the step with the new selector.
        """
        try:
            screenshot = await page.screenshot()

            new_selector = await self._llm_brain.find_element(screenshot, step)
            if not new_selector:
                logger.info("LLM could not find element, moving to escalation")
                return None

            # Create a modified step with the new selector
            adapted_step = step.model_copy(update={"selector": new_selector})

            action_result = await self._action_engine.execute(page, adapted_step)
            if action_result.success:
                self._stats["llm_adapt_success"] += 1
                self._log_operation(
                    step, "llm_adapt", resolved=True,
                    context=context,
                    extra={"new_selector": new_selector},
                )
                return RecoveryResult(
                    resolved=True,
                    strategy_used="llm_adapt",
                    action_result=action_result,
                )
        except Exception as e:
            logger.debug(
                "LLM adapt failed",
                extra={"error": str(e), "step_index": context.get("step_index")},
            )

        return None

    # =========================================================================
    # Tier 3: Escalate to Human
    # =========================================================================

    async def _try_escalate(
        self,
        page: Page,
        step: Step,
        original_error: Exception,
        context: dict[str, Any],
    ) -> RecoveryResult:
        """Tier 3: Escalate to a human checkpoint.

        Creates a checkpoint with the error context, shows the user
        what happened, and asks them to either fix it manually and
        continue, or abort the workflow.
        """
        try:
            screenshot = await page.screenshot()
        except Exception:
            screenshot = None

        # Build an escalation step for the checkpoint manager
        escalation_step = Step(
            type=StepType.CHECKPOINT,
            message=(
                f"⚠️ Recovery needed at step {context.get('step_index', '?')}: "
                f"{step.description or step.type.value} failed.\n"
                f"Error: {str(original_error)}\n"
                f"Please fix manually and approve to continue, or reject to abort."
            ),
        )

        checkpoint_result = await self._checkpoint_manager.request_approval(
            step=escalation_step,
            screenshot=screenshot,
            context=context,
        )

        if checkpoint_result.approved:
            self._stats["escalate_success"] += 1
            self._log_operation(step, "escalate", resolved=True, context=context)
            return RecoveryResult(
                resolved=True,
                strategy_used="escalate",
            )
        else:
            self._stats["unresolved"] += 1
            self._log_operation(
                step, "escalate", resolved=False,
                error="User rejected escalation",
                context=context,
            )
            return RecoveryResult(
                resolved=False,
                strategy_used="escalate",
                error=f"User rejected recovery at step {context.get('step_index')}: "
                      f"{checkpoint_result.reason or 'no reason given'}",
            )

    # =========================================================================
    # Compound Engineering — Logging & Lessons
    # =========================================================================

    def get_stats(self) -> dict[str, int]:
        """Return recovery statistics."""
        return dict(self._stats)

    def get_lessons(self) -> list[dict[str, Any]]:
        """Return lessons from failed recovery attempts.

        Following compound-engineering pattern: failures become lessons
        that improve future recovery strategies.
        """
        return [
            op for op in self._operation_log
            if not op.get("resolved", True)
        ]

    def _log_operation(
        self,
        step: Step,
        strategy: str,
        resolved: bool,
        error: str | None = None,
        context: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Log a recovery operation for analysis."""
        ctx = context or {}
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step_index": ctx.get("step_index"),
            "step_type": step.type.value,
            "strategy": strategy,
            "resolved": resolved,
        }

        if error:
            entry["error"] = error
        if step.description:
            entry["step_description"] = step.description
        if extra:
            entry.update(extra)

        self._operation_log.append(entry)

        logger.info(
            "Recovery operation",
            extra=entry,
        )
