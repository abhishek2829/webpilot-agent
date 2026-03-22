"""Tests for WebPilot Agent — Recovery Engine.

Following TDD discipline: tests written FIRST, then verified against implementation.
Covers: three-tier recovery (retry → LLM adapt → escalate), error classification,
compound-engineering lessons, and edge cases.

The Recovery Engine is the agent's emergency procedure:
  Tier 1: Retry — same action, fresh try (handles transient failures)
  Tier 2: LLM Adapt — ask Claude to find a new selector (handles UI changes)
  Tier 3: Escalate — show the user and ask for help (handles unknown failures)

Analogy: Like a pilot's emergency checklist:
  - Engine sputter? → Try restarting (retry)
  - Engine dead? → Ask copilot for alternatives (LLM adapt)
  - Nothing works? → Radio the tower (escalate to human)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.models import (
    CheckpointResult,
    Step,
    StepType,
    FallbackStrategy,
)
from src.browser.actions import ActionError, ActionResult, ElementNotFoundError


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def click_step() -> Step:
    """A click step with LLM vision fallback."""
    return Step(
        type=StepType.CLICK,
        selector="button.create-app",
        description="Click the Create Application button",
        fallback_strategy=FallbackStrategy.LLM_VISION,
        max_retries=2,
    )


@pytest.fixture
def click_step_retry_only() -> Step:
    """A click step with retry-only fallback (no LLM)."""
    return Step(
        type=StepType.CLICK,
        selector="button.submit",
        description="Click submit",
        fallback_strategy=FallbackStrategy.RETRY,
        max_retries=2,
    )


@pytest.fixture
def click_step_fail_fast() -> Step:
    """A click step that should fail immediately."""
    return Step(
        type=StepType.CLICK,
        selector="button.important",
        description="Click important button",
        fallback_strategy=FallbackStrategy.FAIL,
        max_retries=0,
    )


@pytest.fixture
def optional_step() -> Step:
    """An optional step that can be skipped."""
    return Step(
        type=StepType.CLICK,
        selector="button.optional",
        description="Optional click",
        fallback_strategy=FallbackStrategy.SKIP,
        optional=True,
    )


@pytest.fixture
def mock_page():
    """Mock Playwright page."""
    page = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"fake-screenshot-data")
    return page


@pytest.fixture
def mock_action_engine():
    """Mock action engine that can succeed or fail."""
    engine = AsyncMock()
    engine.execute = AsyncMock(
        return_value=ActionResult(success=True, duration_ms=100)
    )
    return engine


@pytest.fixture
def mock_llm_brain():
    """Mock LLM brain for adaptive recovery."""
    brain = AsyncMock()
    brain.find_element = AsyncMock(return_value="button.new-selector")
    brain.understand_page = AsyncMock(return_value="A dashboard page with a create button in the top right")
    return brain


@pytest.fixture
def mock_checkpoint_manager():
    """Mock checkpoint manager for escalation."""
    mgr = AsyncMock()
    mgr.request_approval = AsyncMock(
        return_value=CheckpointResult(approved=True, by="user")
    )
    return mgr


# =========================================================================
# Initialization
# =========================================================================

class TestRecoveryEngineInit:

    def test_create_recovery_engine(self, mock_action_engine, mock_llm_brain, mock_checkpoint_manager):
        from src.core.recovery import RecoveryEngine

        engine = RecoveryEngine(
            action_engine=mock_action_engine,
            llm_brain=mock_llm_brain,
            checkpoint_manager=mock_checkpoint_manager,
        )
        assert engine is not None

    def test_create_without_llm_brain(self, mock_action_engine, mock_checkpoint_manager):
        """Recovery engine should work without LLM brain (just retry + escalate)."""
        from src.core.recovery import RecoveryEngine

        engine = RecoveryEngine(
            action_engine=mock_action_engine,
            llm_brain=None,
            checkpoint_manager=mock_checkpoint_manager,
        )
        assert engine is not None


# =========================================================================
# Recovery Result
# =========================================================================

class TestRecoveryResult:

    def test_recovery_result_resolved(self):
        from src.core.recovery import RecoveryResult

        result = RecoveryResult(resolved=True, strategy_used="retry", action_result=None)
        assert result.resolved is True

    def test_recovery_result_unresolved(self):
        from src.core.recovery import RecoveryResult

        result = RecoveryResult(resolved=False, strategy_used="exhausted", error="All strategies failed")
        assert result.resolved is False


# =========================================================================
# Tier 1: Retry
# =========================================================================

class TestRetryRecovery:
    """Tier 1: Retry the same action — handles transient failures."""

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_second_attempt(
        self, click_step, mock_page, mock_action_engine, mock_llm_brain, mock_checkpoint_manager
    ):
        from src.core.recovery import RecoveryEngine

        engine = RecoveryEngine(
            action_engine=mock_action_engine,
            llm_brain=mock_llm_brain,
            checkpoint_manager=mock_checkpoint_manager,
        )

        error = ActionError(click_step, "Element not visible")
        result = await engine.handle(mock_page, click_step, error, context={"step_index": 0, "execution_id": "test"})
        assert result.resolved is True
        assert result.strategy_used == "retry"

    @pytest.mark.asyncio
    async def test_retry_uses_action_engine(
        self, click_step, mock_page, mock_action_engine, mock_llm_brain, mock_checkpoint_manager
    ):
        from src.core.recovery import RecoveryEngine

        engine = RecoveryEngine(
            action_engine=mock_action_engine,
            llm_brain=mock_llm_brain,
            checkpoint_manager=mock_checkpoint_manager,
        )

        error = ActionError(click_step, "Timeout")
        await engine.handle(mock_page, click_step, error, context={"step_index": 0, "execution_id": "test"})
        mock_action_engine.execute.assert_called()


# =========================================================================
# Tier 2: LLM Adapt
# =========================================================================

class TestLLMAdaptRecovery:
    """Tier 2: Ask the LLM to find a new selector — handles UI changes."""

    @pytest.mark.asyncio
    async def test_llm_adapt_when_retry_fails(
        self, click_step, mock_page, mock_llm_brain, mock_checkpoint_manager
    ):
        from src.core.recovery import RecoveryEngine

        # Action engine always fails on retry
        failing_engine = AsyncMock()
        failing_engine.execute = AsyncMock(side_effect=ActionError(click_step, "Still not found"))

        engine = RecoveryEngine(
            action_engine=failing_engine,
            llm_brain=mock_llm_brain,
            checkpoint_manager=mock_checkpoint_manager,
        )

        error = ElementNotFoundError(click_step, "Selector not found")
        result = await engine.handle(mock_page, click_step, error, context={"step_index": 0, "execution_id": "test"})

        # LLM brain should have been called to find a new selector
        mock_llm_brain.find_element.assert_called()

    @pytest.mark.asyncio
    async def test_llm_adapt_skipped_when_no_brain(
        self, click_step, mock_page, mock_checkpoint_manager
    ):
        """Without LLM brain, skip straight from retry to escalation."""
        from src.core.recovery import RecoveryEngine

        failing_engine = AsyncMock()
        failing_engine.execute = AsyncMock(side_effect=ActionError(click_step, "Failed"))

        engine = RecoveryEngine(
            action_engine=failing_engine,
            llm_brain=None,
            checkpoint_manager=mock_checkpoint_manager,
        )

        error = ActionError(click_step, "Failed")
        result = await engine.handle(mock_page, click_step, error, context={"step_index": 0, "execution_id": "test"})

        # Should have escalated to checkpoint since LLM not available
        mock_checkpoint_manager.request_approval.assert_called()

    @pytest.mark.asyncio
    async def test_llm_adapt_not_used_for_retry_strategy(
        self, click_step_retry_only, mock_page, mock_llm_brain, mock_checkpoint_manager
    ):
        """Steps with fallback_strategy=retry should NOT use LLM adapt."""
        from src.core.recovery import RecoveryEngine

        failing_engine = AsyncMock()
        failing_engine.execute = AsyncMock(
            side_effect=ActionError(click_step_retry_only, "Failed")
        )

        engine = RecoveryEngine(
            action_engine=failing_engine,
            llm_brain=mock_llm_brain,
            checkpoint_manager=mock_checkpoint_manager,
        )

        error = ActionError(click_step_retry_only, "Failed")
        await engine.handle(mock_page, click_step_retry_only, error, context={"step_index": 0, "execution_id": "test"})

        # LLM brain should NOT have been called
        mock_llm_brain.find_element.assert_not_called()


# =========================================================================
# Tier 3: Escalate to Checkpoint
# =========================================================================

class TestEscalateRecovery:
    """Tier 3: Ask the human for help — the last resort."""

    @pytest.mark.asyncio
    async def test_escalate_when_all_else_fails(
        self, click_step, mock_page, mock_llm_brain, mock_checkpoint_manager
    ):
        from src.core.recovery import RecoveryEngine

        # Both retry and LLM adapt fail
        failing_engine = AsyncMock()
        failing_engine.execute = AsyncMock(side_effect=ActionError(click_step, "Failed"))
        mock_llm_brain.find_element = AsyncMock(return_value=None)  # LLM can't find it

        engine = RecoveryEngine(
            action_engine=failing_engine,
            llm_brain=mock_llm_brain,
            checkpoint_manager=mock_checkpoint_manager,
        )

        error = ActionError(click_step, "Element not found")
        await engine.handle(mock_page, click_step, error, context={"step_index": 0, "execution_id": "test"})

        mock_checkpoint_manager.request_approval.assert_called()

    @pytest.mark.asyncio
    async def test_escalate_user_approves_continues(
        self, click_step, mock_page, mock_llm_brain, mock_checkpoint_manager
    ):
        from src.core.recovery import RecoveryEngine

        failing_engine = AsyncMock()
        failing_engine.execute = AsyncMock(side_effect=ActionError(click_step, "Failed"))
        mock_llm_brain.find_element = AsyncMock(return_value=None)

        mock_checkpoint_manager.request_approval = AsyncMock(
            return_value=CheckpointResult(approved=True, by="user", reason="I fixed it manually")
        )

        engine = RecoveryEngine(
            action_engine=failing_engine,
            llm_brain=mock_llm_brain,
            checkpoint_manager=mock_checkpoint_manager,
        )

        error = ActionError(click_step, "Failed")
        result = await engine.handle(mock_page, click_step, error, context={"step_index": 0, "execution_id": "test"})

        assert result.resolved is True
        assert result.strategy_used == "escalate"

    @pytest.mark.asyncio
    async def test_escalate_user_rejects_unresolved(
        self, click_step, mock_page, mock_llm_brain, mock_checkpoint_manager
    ):
        from src.core.recovery import RecoveryEngine

        failing_engine = AsyncMock()
        failing_engine.execute = AsyncMock(side_effect=ActionError(click_step, "Failed"))
        mock_llm_brain.find_element = AsyncMock(return_value=None)

        mock_checkpoint_manager.request_approval = AsyncMock(
            return_value=CheckpointResult(approved=False, by="user", reason="Abort")
        )

        engine = RecoveryEngine(
            action_engine=failing_engine,
            llm_brain=mock_llm_brain,
            checkpoint_manager=mock_checkpoint_manager,
        )

        error = ActionError(click_step, "Failed")
        result = await engine.handle(mock_page, click_step, error, context={"step_index": 0, "execution_id": "test"})

        assert result.resolved is False


# =========================================================================
# Fail-Fast Strategy
# =========================================================================

class TestFailFastStrategy:
    """Steps with fallback_strategy=fail should not attempt recovery."""

    @pytest.mark.asyncio
    async def test_fail_fast_no_recovery(
        self, click_step_fail_fast, mock_page, mock_action_engine, mock_llm_brain, mock_checkpoint_manager
    ):
        from src.core.recovery import RecoveryEngine

        engine = RecoveryEngine(
            action_engine=mock_action_engine,
            llm_brain=mock_llm_brain,
            checkpoint_manager=mock_checkpoint_manager,
        )

        error = ActionError(click_step_fail_fast, "Failed")
        result = await engine.handle(mock_page, click_step_fail_fast, error, context={"step_index": 0, "execution_id": "test"})

        assert result.resolved is False
        assert result.strategy_used == "fail"
        mock_action_engine.execute.assert_not_called()


# =========================================================================
# Skip Strategy
# =========================================================================

class TestSkipStrategy:
    """Optional steps with fallback_strategy=skip should resolve by skipping."""

    @pytest.mark.asyncio
    async def test_skip_optional_resolves(
        self, optional_step, mock_page, mock_action_engine, mock_llm_brain, mock_checkpoint_manager
    ):
        from src.core.recovery import RecoveryEngine

        engine = RecoveryEngine(
            action_engine=mock_action_engine,
            llm_brain=mock_llm_brain,
            checkpoint_manager=mock_checkpoint_manager,
        )

        error = ActionError(optional_step, "Not found")
        result = await engine.handle(mock_page, optional_step, error, context={"step_index": 0, "execution_id": "test"})

        assert result.resolved is True
        assert result.strategy_used == "skip"


# =========================================================================
# Compound Engineering
# =========================================================================

class TestRecoveryCompoundEngineering:
    """Recovery attempts tracked for self-improvement."""

    @pytest.mark.asyncio
    async def test_stats_tracked(
        self, click_step, mock_page, mock_action_engine, mock_llm_brain, mock_checkpoint_manager
    ):
        from src.core.recovery import RecoveryEngine

        engine = RecoveryEngine(
            action_engine=mock_action_engine,
            llm_brain=mock_llm_brain,
            checkpoint_manager=mock_checkpoint_manager,
        )

        error = ActionError(click_step, "Failed")
        await engine.handle(mock_page, click_step, error, context={"step_index": 0, "execution_id": "test"})

        stats = engine.get_stats()
        assert stats["total_recoveries"] >= 1

    @pytest.mark.asyncio
    async def test_lessons_from_failures(
        self, click_step_fail_fast, mock_page, mock_action_engine, mock_llm_brain, mock_checkpoint_manager
    ):
        from src.core.recovery import RecoveryEngine

        engine = RecoveryEngine(
            action_engine=mock_action_engine,
            llm_brain=mock_llm_brain,
            checkpoint_manager=mock_checkpoint_manager,
        )

        error = ActionError(click_step_fail_fast, "Critical failure")
        await engine.handle(mock_page, click_step_fail_fast, error, context={"step_index": 0, "execution_id": "test"})

        lessons = engine.get_lessons()
        assert len(lessons) >= 1
