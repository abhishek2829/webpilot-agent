"""WebPilot Agent — Checkpoint Manager.

The human-in-the-loop gate for workflow execution. When a workflow hits
a checkpoint step, execution pauses and the manager asks a human for
approval before continuing.

Analogy: A toll booth on a highway. The car (workflow) drives up, stops,
and the driver (human) decides whether to proceed or turn back. Three
types of toll booths:
  - CLI: staffed booth, you talk to a person (terminal input)
  - WebSocket: E-ZPass sensor, approval comes from a dashboard
  - Auto: open highway, no stopping (for trusted workflows)

Patterns applied:
- gsd-checkpoint-protocol: 3 checkpoint types (human-verify, decision, human-action)
- compound-engineering: every checkpoint logged for lessons/stats
- autoresearch: track approval/rejection rates per workflow step
"""

from __future__ import annotations

import asyncio
import base64
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from src.core.models import CheckpointEvent, CheckpointResult, Step

logger = logging.getLogger(__name__)

# Type alias for WebSocket approval handlers
ApprovalHandler = Callable[[CheckpointEvent], Awaitable[CheckpointResult]]

VALID_MODES = {"cli", "websocket", "auto"}


class CheckpointError(Exception):
    """Base exception for checkpoint operations."""
    pass


class CheckpointTimeoutError(CheckpointError):
    """Raised when a checkpoint times out waiting for a response."""
    pass


class CheckpointManager:
    """Manages human-in-the-loop checkpoints during workflow execution.

    Three modes of operation:
      - "cli": Prints checkpoint info to terminal, waits for y/n input
      - "websocket": Pushes checkpoint event to a handler (dashboard), waits for response
      - "auto": Instantly approves all checkpoints (for trusted/tested workflows)

    Usage:
        mgr = CheckpointManager(mode="cli", timeout_seconds=300)
        result = await mgr.request_approval(step, screenshot, context)
        if result.approved:
            # continue execution
        else:
            # abort workflow

    Thread safety: One manager per execution. Don't share across concurrent workflows.
    """

    def __init__(
        self,
        mode: str = "cli",
        timeout_seconds: int = 300,
    ) -> None:
        if mode not in VALID_MODES:
            raise ValueError(
                f"mode must be one of {VALID_MODES}, got '{mode}'"
            )
        self._mode = mode
        self._timeout_seconds = timeout_seconds

        # WebSocket mode: external approval handler
        self._approval_handler: ApprovalHandler | None = None

        # Compound-engineering: log every checkpoint interaction
        self._event_log: list[CheckpointEvent] = []
        self._operation_log: list[dict[str, Any]] = []

        # Stats tracking
        self._stats = {
            "total_checkpoints": 0,
            "approved": 0,
            "rejected": 0,
            "timed_out": 0,
        }

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def timeout_seconds(self) -> int:
        return self._timeout_seconds

    # =========================================================================
    # Main Entry Point
    # =========================================================================

    async def request_approval(
        self,
        step: Step,
        screenshot: bytes | None,
        context: dict[str, Any],
    ) -> CheckpointResult:
        """Pause execution and wait for human approval.

        Args:
            step: The checkpoint Step from the workflow
            screenshot: Screenshot bytes (PNG), or None if unavailable
            context: Execution context with execution_id, step_index, variables

        Returns:
            CheckpointResult with approved=True/False and metadata
        """
        # Build the checkpoint event
        event = CheckpointEvent(
            execution_id=context.get("execution_id", "unknown"),
            step_index=context.get("step_index", -1),
            message=step.message or "",
            screenshot_b64=(
                base64.b64encode(screenshot).decode() if screenshot else None
            ),
            variables=context.get("variables", {}),
        )

        # Log the event
        self._event_log.append(event)
        self._stats["total_checkpoints"] += 1

        logger.info(
            "Checkpoint requested",
            extra={
                "mode": self._mode,
                "step_index": event.step_index,
                "execution_id": event.execution_id,
                "message": event.message,
            },
        )

        # Dispatch to the appropriate handler
        try:
            if self._mode == "auto":
                result = await self._auto_approval(event)
            elif self._mode == "cli":
                result = await self._cli_approval(event)
            elif self._mode == "websocket":
                result = await self._ws_approval(event)
            else:
                raise CheckpointError(f"Unknown mode: {self._mode}")
        except CheckpointTimeoutError:
            self._stats["timed_out"] += 1
            self._log_operation(event, None, error="timeout")
            raise

        # Update stats
        if result.approved:
            self._stats["approved"] += 1
        else:
            self._stats["rejected"] += 1

        # Log operation for compound-engineering
        self._log_operation(event, result)

        return result

    # =========================================================================
    # Mode Handlers
    # =========================================================================

    async def _auto_approval(self, event: CheckpointEvent) -> CheckpointResult:
        """Auto-approve mode: instantly approve all checkpoints."""
        logger.info(
            "Auto-approved checkpoint",
            extra={"step_index": event.step_index},
        )
        return CheckpointResult(approved=True, by="auto")

    async def _cli_approval(self, event: CheckpointEvent) -> CheckpointResult:
        """CLI mode: print checkpoint info and wait for y/n input.

        Runs the blocking input() call in a thread executor so it doesn't
        block the event loop.
        """
        # Display checkpoint info
        print("\n" + "=" * 60)
        print("🔔 CHECKPOINT")
        print("=" * 60)
        print(f"Step {event.step_index}: {event.message}")
        if event.variables:
            print(f"Variables: {event.variables}")
        if event.screenshot_b64:
            print("📸 Screenshot captured")
        print("=" * 60)

        # Get user input (run in executor to avoid blocking the event loop)
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: input("Continue? (y/n): "),
        )

        approved = response.strip().lower() in ("y", "yes")

        return CheckpointResult(
            approved=approved,
            by="user",
            reason=None if approved else f"User responded: {response}",
        )

    async def _ws_approval(self, event: CheckpointEvent) -> CheckpointResult:
        """WebSocket mode: push event to handler, wait for response with timeout."""
        if self._approval_handler is None:
            raise CheckpointError(
                "No approval handler set for WebSocket mode. "
                "Call set_approval_handler() before requesting approval."
            )

        try:
            result = await asyncio.wait_for(
                self._approval_handler(event),
                timeout=self._timeout_seconds,
            )
            return result
        except asyncio.TimeoutError:
            raise CheckpointTimeoutError(
                f"Checkpoint timed out after {self._timeout_seconds}s "
                f"waiting for approval at step {event.step_index}"
            )

    # =========================================================================
    # WebSocket Handler Registration
    # =========================================================================

    def set_approval_handler(self, handler: ApprovalHandler) -> None:
        """Register an external approval handler for WebSocket mode.

        The handler receives a CheckpointEvent and must return a CheckpointResult.
        This is typically connected to a WebSocket endpoint that pushes the event
        to a dashboard and waits for the user's response.

        Args:
            handler: Async callable (CheckpointEvent) -> CheckpointResult
        """
        self._approval_handler = handler

    # =========================================================================
    # Compound Engineering — Logging & Lessons
    # =========================================================================

    def get_event_log(self) -> list[CheckpointEvent]:
        """Return all checkpoint events that have been created."""
        return list(self._event_log)

    def get_stats(self) -> dict[str, int]:
        """Return checkpoint statistics."""
        return dict(self._stats)

    def get_lessons(self) -> list[dict[str, Any]]:
        """Return lessons from failed/rejected checkpoints.

        Following compound-engineering pattern: failures become lessons
        that can improve future workflows (e.g., "step 5 in clerk-setup
        always gets rejected → workflow needs redesign").
        """
        return [
            op for op in self._operation_log
            if op.get("outcome") in ("rejected", "error", "timeout")
        ]

    def _log_operation(
        self,
        event: CheckpointEvent,
        result: CheckpointResult | None,
        error: str | None = None,
    ) -> None:
        """Log a checkpoint operation for compound-engineering analysis."""
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": self._mode,
            "execution_id": event.execution_id,
            "step_index": event.step_index,
            "message": event.message,
        }

        if error:
            entry["outcome"] = "error"
            entry["error"] = error
        elif result:
            entry["outcome"] = "approved" if result.approved else "rejected"
            entry["approved"] = result.approved
            entry["by"] = result.by
            if result.reason:
                entry["reason"] = result.reason
        else:
            entry["outcome"] = "unknown"

        self._operation_log.append(entry)

        logger.debug(
            "Checkpoint operation logged",
            extra=entry,
        )
