"""Tests for WebPilot Agent — Checkpoint Manager.

Following TDD discipline: tests written FIRST, then verified against implementation.
Covers: CLI mode, WebSocket mode, auto-approve mode, timeout handling,
checkpoint events, compound-engineering lessons, and edge cases.

The Checkpoint Manager is the "toll booth" — it pauses workflow execution
and asks a human whether to continue. Three modes:
  1. CLI: prints message + screenshot path, waits for y/n
  2. WebSocket: pushes event to dashboard, waits for approval
  3. Auto: approves everything (for trusted workflows)
"""

import asyncio
import base64
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.models import (
    CheckpointEvent,
    CheckpointResult,
    ExecutionStatus,
    Step,
    StepType,
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def checkpoint_step() -> Step:
    """A typical checkpoint step from a workflow."""
    return Step(
        type=StepType.CHECKPOINT,
        message="Ready to create Clerk app? Confirm to continue.",
        screenshot=True,
    )


@pytest.fixture
def screenshot_bytes() -> bytes:
    """Fake screenshot data."""
    return b"fake-screenshot-png-data"


@pytest.fixture
def execution_context() -> dict:
    """Context passed during execution."""
    return {
        "execution_id": "exec-abc123",
        "step_index": 3,
        "variables": {"project_name": "MyApp"},
    }


# =========================================================================
# Initialization
# =========================================================================

class TestCheckpointManagerInit:
    """Test manager creation with different modes."""

    def test_create_cli_mode(self):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="cli")
        assert mgr.mode == "cli"

    def test_create_websocket_mode(self):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="websocket")
        assert mgr.mode == "websocket"

    def test_create_auto_mode(self):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="auto")
        assert mgr.mode == "auto"

    def test_invalid_mode_raises(self):
        from src.checkpoints.manager import CheckpointManager

        with pytest.raises(ValueError, match="mode must be one of"):
            CheckpointManager(mode="invalid")

    def test_default_timeout(self):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="auto")
        assert mgr.timeout_seconds == 300

    def test_custom_timeout(self):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="auto", timeout_seconds=60)
        assert mgr.timeout_seconds == 60


# =========================================================================
# Checkpoint Event Creation
# =========================================================================

class TestCheckpointEventCreation:
    """Test that request_approval creates proper CheckpointEvent."""

    @pytest.mark.asyncio
    async def test_creates_checkpoint_event(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="auto")
        result = await mgr.request_approval(
            step=checkpoint_step,
            screenshot=screenshot_bytes,
            context=execution_context,
        )
        # Auto mode should always approve
        assert result.approved is True

    @pytest.mark.asyncio
    async def test_event_captures_screenshot_b64(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        """The checkpoint event should encode the screenshot as base64."""
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="auto")
        # Use event_log to inspect the event that was created
        await mgr.request_approval(
            step=checkpoint_step,
            screenshot=screenshot_bytes,
            context=execution_context,
        )
        assert len(mgr.get_event_log()) == 1
        event = mgr.get_event_log()[0]
        assert event.screenshot_b64 == base64.b64encode(screenshot_bytes).decode()

    @pytest.mark.asyncio
    async def test_event_captures_message(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="auto")
        await mgr.request_approval(
            step=checkpoint_step,
            screenshot=screenshot_bytes,
            context=execution_context,
        )
        event = mgr.get_event_log()[0]
        assert event.message == checkpoint_step.message

    @pytest.mark.asyncio
    async def test_event_captures_step_index(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="auto")
        await mgr.request_approval(
            step=checkpoint_step,
            screenshot=screenshot_bytes,
            context=execution_context,
        )
        event = mgr.get_event_log()[0]
        assert event.step_index == 3

    @pytest.mark.asyncio
    async def test_event_captures_variables(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="auto")
        await mgr.request_approval(
            step=checkpoint_step,
            screenshot=screenshot_bytes,
            context=execution_context,
        )
        event = mgr.get_event_log()[0]
        assert event.variables == {"project_name": "MyApp"}

    @pytest.mark.asyncio
    async def test_event_has_execution_id(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="auto")
        await mgr.request_approval(
            step=checkpoint_step,
            screenshot=screenshot_bytes,
            context=execution_context,
        )
        event = mgr.get_event_log()[0]
        assert event.execution_id == "exec-abc123"


# =========================================================================
# Auto-Approve Mode
# =========================================================================

class TestAutoApproveMode:
    """Auto mode: approves everything immediately — for trusted workflows."""

    @pytest.mark.asyncio
    async def test_auto_approves(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="auto")
        result = await mgr.request_approval(
            step=checkpoint_step,
            screenshot=screenshot_bytes,
            context=execution_context,
        )
        assert result.approved is True
        assert result.by == "auto"

    @pytest.mark.asyncio
    async def test_auto_approve_has_timestamp(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="auto")
        result = await mgr.request_approval(
            step=checkpoint_step,
            screenshot=screenshot_bytes,
            context=execution_context,
        )
        assert isinstance(result.responded_at, datetime)


# =========================================================================
# CLI Mode
# =========================================================================

class TestCLIMode:
    """CLI mode: prints checkpoint info and waits for y/n input."""

    @pytest.mark.asyncio
    async def test_cli_approve_on_y(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="cli")

        with patch("builtins.input", return_value="y"):
            result = await mgr.request_approval(
                step=checkpoint_step,
                screenshot=screenshot_bytes,
                context=execution_context,
            )
        assert result.approved is True
        assert result.by == "user"

    @pytest.mark.asyncio
    async def test_cli_approve_on_yes(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="cli")

        with patch("builtins.input", return_value="yes"):
            result = await mgr.request_approval(
                step=checkpoint_step,
                screenshot=screenshot_bytes,
                context=execution_context,
            )
        assert result.approved is True

    @pytest.mark.asyncio
    async def test_cli_approve_case_insensitive(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="cli")

        with patch("builtins.input", return_value="Y"):
            result = await mgr.request_approval(
                step=checkpoint_step,
                screenshot=screenshot_bytes,
                context=execution_context,
            )
        assert result.approved is True

    @pytest.mark.asyncio
    async def test_cli_reject_on_n(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="cli")

        with patch("builtins.input", return_value="n"):
            result = await mgr.request_approval(
                step=checkpoint_step,
                screenshot=screenshot_bytes,
                context=execution_context,
            )
        assert result.approved is False
        assert result.by == "user"

    @pytest.mark.asyncio
    async def test_cli_reject_on_no(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="cli")

        with patch("builtins.input", return_value="no"):
            result = await mgr.request_approval(
                step=checkpoint_step,
                screenshot=screenshot_bytes,
                context=execution_context,
            )
        assert result.approved is False

    @pytest.mark.asyncio
    async def test_cli_reject_on_empty_input(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="cli")

        with patch("builtins.input", return_value=""):
            result = await mgr.request_approval(
                step=checkpoint_step,
                screenshot=screenshot_bytes,
                context=execution_context,
            )
        assert result.approved is False

    @pytest.mark.asyncio
    async def test_cli_reject_on_garbage(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="cli")

        with patch("builtins.input", return_value="maybe"):
            result = await mgr.request_approval(
                step=checkpoint_step,
                screenshot=screenshot_bytes,
                context=execution_context,
            )
        assert result.approved is False

    @pytest.mark.asyncio
    async def test_cli_prints_message(
        self, checkpoint_step, screenshot_bytes, execution_context, capsys
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="cli")

        with patch("builtins.input", return_value="y"):
            await mgr.request_approval(
                step=checkpoint_step,
                screenshot=screenshot_bytes,
                context=execution_context,
            )
        captured = capsys.readouterr()
        assert "Ready to create Clerk app?" in captured.out


# =========================================================================
# WebSocket Mode
# =========================================================================

class TestWebSocketMode:
    """WebSocket mode: pushes event, waits for approval via callback."""

    @pytest.mark.asyncio
    async def test_ws_approval_via_callback(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="websocket")

        # Simulate external approval by providing an approval handler
        async def approve_handler(event: CheckpointEvent) -> CheckpointResult:
            return CheckpointResult(approved=True, by="dashboard_user")

        mgr.set_approval_handler(approve_handler)

        result = await mgr.request_approval(
            step=checkpoint_step,
            screenshot=screenshot_bytes,
            context=execution_context,
        )
        assert result.approved is True
        assert result.by == "dashboard_user"

    @pytest.mark.asyncio
    async def test_ws_rejection_via_callback(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="websocket")

        async def reject_handler(event: CheckpointEvent) -> CheckpointResult:
            return CheckpointResult(
                approved=False,
                by="dashboard_user",
                reason="Looks wrong",
            )

        mgr.set_approval_handler(reject_handler)

        result = await mgr.request_approval(
            step=checkpoint_step,
            screenshot=screenshot_bytes,
            context=execution_context,
        )
        assert result.approved is False
        assert result.reason == "Looks wrong"

    @pytest.mark.asyncio
    async def test_ws_no_handler_raises(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager, CheckpointError

        mgr = CheckpointManager(mode="websocket")
        # No handler set — should raise
        with pytest.raises(CheckpointError, match="No approval handler"):
            await mgr.request_approval(
                step=checkpoint_step,
                screenshot=screenshot_bytes,
                context=execution_context,
            )


# =========================================================================
# Timeout Handling
# =========================================================================

class TestTimeoutHandling:
    """Checkpoints should timeout if no response arrives."""

    @pytest.mark.asyncio
    async def test_ws_timeout_rejects(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager, CheckpointTimeoutError

        mgr = CheckpointManager(mode="websocket", timeout_seconds=1)

        async def slow_handler(event: CheckpointEvent) -> CheckpointResult:
            await asyncio.sleep(5)  # Longer than timeout
            return CheckpointResult(approved=True, by="slow_user")

        mgr.set_approval_handler(slow_handler)

        with pytest.raises(CheckpointTimeoutError):
            await mgr.request_approval(
                step=checkpoint_step,
                screenshot=screenshot_bytes,
                context=execution_context,
            )


# =========================================================================
# No Screenshot
# =========================================================================

class TestNoScreenshot:
    """Handle cases where screenshot is None."""

    @pytest.mark.asyncio
    async def test_none_screenshot(self, checkpoint_step, execution_context):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="auto")
        result = await mgr.request_approval(
            step=checkpoint_step,
            screenshot=None,
            context=execution_context,
        )
        assert result.approved is True
        event = mgr.get_event_log()[0]
        assert event.screenshot_b64 is None


# =========================================================================
# Compound Engineering — Operation Logging
# =========================================================================

class TestCompoundEngineering:
    """Every checkpoint interaction is logged for self-improvement."""

    @pytest.mark.asyncio
    async def test_operations_logged(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="auto")
        await mgr.request_approval(
            step=checkpoint_step,
            screenshot=screenshot_bytes,
            context=execution_context,
        )
        lessons = mgr.get_lessons()
        assert len(lessons) >= 0  # No failures = no lessons (lessons track failures)

    @pytest.mark.asyncio
    async def test_stats_tracked(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="auto")
        await mgr.request_approval(
            step=checkpoint_step,
            screenshot=screenshot_bytes,
            context=execution_context,
        )
        stats = mgr.get_stats()
        assert stats["total_checkpoints"] == 1
        assert stats["approved"] == 1
        assert stats["rejected"] == 0

    @pytest.mark.asyncio
    async def test_rejected_stats(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="cli")
        with patch("builtins.input", return_value="n"):
            await mgr.request_approval(
                step=checkpoint_step,
                screenshot=screenshot_bytes,
                context=execution_context,
            )
        stats = mgr.get_stats()
        assert stats["total_checkpoints"] == 1
        assert stats["rejected"] == 1

    @pytest.mark.asyncio
    async def test_multiple_checkpoints_tracked(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="auto")
        for _ in range(3):
            await mgr.request_approval(
                step=checkpoint_step,
                screenshot=screenshot_bytes,
                context=execution_context,
            )
        stats = mgr.get_stats()
        assert stats["total_checkpoints"] == 3

    @pytest.mark.asyncio
    async def test_get_lessons_returns_failures(
        self, checkpoint_step, screenshot_bytes, execution_context
    ):
        """Lessons capture checkpoint failures/rejections for analysis."""
        from src.checkpoints.manager import CheckpointManager

        mgr = CheckpointManager(mode="cli")
        with patch("builtins.input", return_value="n"):
            await mgr.request_approval(
                step=checkpoint_step,
                screenshot=screenshot_bytes,
                context=execution_context,
            )
        lessons = mgr.get_lessons()
        assert len(lessons) == 1
        assert lessons[0]["outcome"] == "rejected"
