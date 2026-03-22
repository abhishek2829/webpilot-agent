"""Tests for Action Engine using mocked Playwright (Task 17 coverage).

Tests ActionEngine dispatch logic, error handling, retry logic,
selector analytics, and compound engineering — all without a real browser.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.browser.actions import (
    ActionEngine,
    ActionError,
    ActionResult,
    ElementNotFoundError,
)
from src.core.models import Step, StepType, FallbackStrategy


# =========================================================================
# Helpers
# =========================================================================

def _make_step(
    step_type: StepType = StepType.CLICK,
    selector: str = "button.submit",
    **kwargs,
) -> Step:
    """Create a Step with common defaults."""
    return Step(type=step_type, selector=selector, **kwargs)


def _mock_page():
    """Create a mock Playwright page."""
    page = AsyncMock()
    element = AsyncMock()

    page.wait_for_selector = AsyncMock(return_value=element)
    page.goto = AsyncMock()
    page.title = AsyncMock(return_value="Test Page")
    page.url = "https://example.com"
    page.wait_for_load_state = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"png_bytes")
    page.evaluate = AsyncMock()

    element.click = AsyncMock()
    element.fill = AsyncMock()
    element.text_content = AsyncMock(return_value="extracted_value")
    element.input_value = AsyncMock(return_value="input_val")
    element.get_attribute = AsyncMock(return_value="attr_val")
    element.is_visible = AsyncMock(return_value=True)
    element.scroll_into_view_if_needed = AsyncMock()
    element.select_option = AsyncMock()

    return page, element


# =========================================================================
# Test: ActionResult
# =========================================================================

class TestActionResult:
    """Test ActionResult data class."""

    def test_success_result(self):
        r = ActionResult(success=True, data={"key": "val"})
        assert r.success is True
        assert r.data == {"key": "val"}
        assert r.error is None

    def test_failure_result(self):
        r = ActionResult(success=False, error="timeout")
        assert r.success is False
        assert r.error == "timeout"

    def test_extracted_value(self):
        r = ActionResult(success=True, extracted_value="pk_live_123")
        assert r.extracted_value == "pk_live_123"

    def test_default_strategy(self):
        r = ActionResult(success=True)
        assert r.strategy_used == "selector"


# =========================================================================
# Test: ActionError / ElementNotFoundError
# =========================================================================

class TestActionErrors:
    """Test custom exception classes."""

    def test_action_error_carries_step(self):
        step = _make_step()
        err = ActionError(step=step, message="Click failed")
        assert err.step is step
        assert str(err) == "Click failed"

    def test_action_error_optional_screenshot(self):
        step = _make_step()
        err = ActionError(step=step, message="fail", screenshot=b"png")
        assert err.screenshot == b"png"

    def test_element_not_found_is_action_error(self):
        step = _make_step()
        err = ElementNotFoundError(step=step, message="not found")
        assert isinstance(err, ActionError)


# =========================================================================
# Test: ActionEngine dispatch
# =========================================================================

class TestActionEngineDispatch:
    """Test that execute dispatches to the correct handler."""

    @pytest.mark.asyncio
    async def test_navigate_step(self):
        engine = ActionEngine()
        page, element = _mock_page()
        step = Step(type=StepType.NAVIGATE, url="https://clerk.com")
        result = await engine.execute(page, step)
        assert result.success is True
        page.goto.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_click_step(self):
        engine = ActionEngine()
        page, element = _mock_page()
        step = _make_step(StepType.CLICK)
        result = await engine.execute(page, step)
        assert result.success is True
        element.click.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_type_step(self):
        engine = ActionEngine()
        page, element = _mock_page()
        step = Step(type=StepType.TYPE, selector="input#name", text="MyApp")
        result = await engine.execute(page, step)
        assert result.success is True
        element.fill.assert_awaited()

    @pytest.mark.asyncio
    async def test_extract_step_text_content(self):
        engine = ActionEngine()
        page, element = _mock_page()
        step = Step(
            type=StepType.EXTRACT,
            selector=".api-key",
            variable="API_KEY",
            extract_attribute="textContent",
        )
        result = await engine.execute(page, step)
        assert result.success is True
        assert result.extracted_value == "extracted_value"

    @pytest.mark.asyncio
    async def test_wait_step_networkidle(self):
        engine = ActionEngine()
        page, element = _mock_page()
        step = Step(type=StepType.WAIT, wait_for="networkidle")
        result = await engine.execute(page, step)
        assert result.success is True
        page.wait_for_load_state.assert_awaited_with("networkidle")

    @pytest.mark.asyncio
    async def test_wait_step_selector(self):
        engine = ActionEngine()
        page, element = _mock_page()
        step = Step(type=StepType.WAIT, wait_for=".loaded")
        result = await engine.execute(page, step)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_wait_step_timeout(self):
        engine = ActionEngine()
        page, element = _mock_page()
        step = Step(type=StepType.WAIT, timeout_seconds=2)
        result = await engine.execute(page, step)
        assert result.success is True
        page.wait_for_timeout.assert_awaited()

    @pytest.mark.asyncio
    async def test_select_step(self):
        engine = ActionEngine()
        page, element = _mock_page()
        step = Step(type=StepType.SELECT, selector="select#country", text="India")
        result = await engine.execute(page, step)
        assert result.success is True
        element.select_option.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_scroll_step_with_selector(self):
        engine = ActionEngine()
        page, element = _mock_page()
        step = _make_step(StepType.SCROLL, selector="#footer")
        result = await engine.execute(page, step)
        assert result.success is True
        element.scroll_into_view_if_needed.assert_awaited()

    @pytest.mark.asyncio
    async def test_scroll_step_page_down(self):
        engine = ActionEngine()
        page, element = _mock_page()
        step = Step(type=StepType.SCROLL)
        result = await engine.execute(page, step)
        assert result.success is True
        page.evaluate.assert_awaited()

    @pytest.mark.asyncio
    async def test_screenshot_step(self):
        engine = ActionEngine()
        page, element = _mock_page()
        step = Step(type=StepType.SCREENSHOT, description="dashboard view")
        result = await engine.execute(page, step)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_checkpoint_passthrough(self):
        engine = ActionEngine()
        page, element = _mock_page()
        step = Step(type=StepType.CHECKPOINT, message="Confirm?")
        result = await engine.execute(page, step)
        assert result.success is True
        assert result.data.get("type") == "checkpoint_passthrough"


# =========================================================================
# Test: Retry and fallback logic
# =========================================================================

class TestActionEngineRetry:
    """Test retry and LLM vision fallback."""

    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        engine = ActionEngine()
        page, element = _mock_page()
        # Fail twice, succeed on third
        page.wait_for_selector = AsyncMock(
            side_effect=[Exception("fail"), Exception("fail"), element]
        )
        step = Step(type=StepType.CLICK, selector="btn", max_retries=2)
        result = await engine.execute(page, step)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_optional_step_returns_success_on_failure(self):
        engine = ActionEngine()
        page, element = _mock_page()
        page.wait_for_selector = AsyncMock(side_effect=Exception("not found"))
        step = Step(type=StepType.CLICK, selector="btn", max_retries=0, optional=True)
        result = await engine.execute(page, step)
        assert result.success is True
        assert result.strategy_used == "skipped"


# =========================================================================
# Test: Selector analytics
# =========================================================================

class TestSelectorAnalytics:
    """Test selector success rate tracking."""

    def test_track_selector_success(self):
        engine = ActionEngine()
        engine._track_selector("button.submit", success=True)
        engine._track_selector("button.submit", success=True)
        engine._track_selector("button.submit", success=False)

        stats = engine.get_selector_stats()
        assert stats["button.submit"]["attempts"] == 3
        assert stats["button.submit"]["successes"] == 2
        assert abs(stats["button.submit"]["success_rate"] - 0.667) < 0.01

    def test_fragile_selectors_empty_initially(self):
        engine = ActionEngine()
        assert engine.get_fragile_selectors() == []

    def test_fragile_selectors_detected(self):
        engine = ActionEngine()
        for _ in range(4):
            engine._track_selector(".fragile", success=False)
        engine._track_selector(".fragile", success=True)

        fragile = engine.get_fragile_selectors(threshold=0.5)
        assert len(fragile) == 1
        assert fragile[0]["selector"] == ".fragile"

    def test_fragile_selectors_ignores_few_attempts(self):
        engine = ActionEngine()
        engine._track_selector(".new", success=False)
        engine._track_selector(".new", success=False)
        # Only 2 attempts, threshold requires >= 3
        fragile = engine.get_fragile_selectors()
        assert len(fragile) == 0


# =========================================================================
# Test: Compound engineering
# =========================================================================

class TestActionEngineCompound:
    """Test operation logging and lessons."""

    @pytest.mark.asyncio
    async def test_operation_log_populated(self):
        engine = ActionEngine()
        page, element = _mock_page()
        step = Step(type=StepType.NAVIGATE, url="https://example.com")
        await engine.execute(page, step)
        log = engine.get_operation_log()
        assert len(log) == 1
        assert log[0]["step_type"] == "navigate"
        assert log[0]["success"] is True

    @pytest.mark.asyncio
    async def test_lessons_captures_failures(self):
        engine = ActionEngine()
        page, element = _mock_page()
        page.wait_for_selector = AsyncMock(side_effect=Exception("timeout"))
        step = Step(type=StepType.CLICK, selector="btn", max_retries=0)
        result = await engine.execute(page, step)
        lessons = engine.get_lessons()
        assert len(lessons) == 1
        assert lessons[0]["success"] is False

    def test_log_truncates_at_500(self):
        engine = ActionEngine()
        step = _make_step()
        for _ in range(550):
            engine._log_op(step, ActionResult(success=True), attempt=0)
        assert len(engine.get_operation_log()) == 500
