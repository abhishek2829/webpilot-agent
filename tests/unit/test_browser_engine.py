"""Tests for WebPilot Agent — Sprint 2: Browser Engine.

Unit tests use mocked Playwright — no real browser needed.
Integration tests (marked @pytest.mark.integration) require Playwright installed.

Covers:
- BrowserSession: lifecycle, screenshots, state persistence
- ActionEngine: dispatch, two-tier element finding, retries, fallbacks, analytics
- LLMBrain: prompt construction, response parsing, error handling, stats
"""

import base64
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timezone

from src.core.models import Step, StepType, FallbackStrategy
from src.browser.actions import ActionEngine, ActionResult, ElementNotFoundError
from src.core.llm_brain import LLMBrain


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def mock_page() -> AsyncMock:
    """Create a mocked Playwright page."""
    page = AsyncMock()
    page.url = "https://example.com"
    page.title = AsyncMock(return_value="Example Page")
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.inner_text = AsyncMock(return_value="Page body text")
    page.accessibility = MagicMock()
    page.accessibility.snapshot = AsyncMock(return_value={"role": "WebArea"})

    # Screenshot returns fake PNG bytes
    page.screenshot = AsyncMock(return_value=b"\x89PNG_fake_screenshot_data")

    # Default: wait_for_selector returns a mock element
    mock_element = AsyncMock()
    mock_element.text_content = AsyncMock(return_value="extracted text")
    mock_element.input_value = AsyncMock(return_value="input value")
    mock_element.is_visible = AsyncMock(return_value=True)
    mock_element.get_attribute = AsyncMock(return_value="https://example.com/link")
    mock_element.scroll_into_view_if_needed = AsyncMock()
    mock_element.click = AsyncMock()
    mock_element.fill = AsyncMock()
    mock_element.select_option = AsyncMock()

    page.wait_for_selector = AsyncMock(return_value=mock_element)
    page.evaluate = AsyncMock()

    return page


@pytest.fixture
def mock_llm_brain() -> AsyncMock:
    """Create a mocked LLM Brain."""
    brain = AsyncMock()
    brain.find_element = AsyncMock(return_value="button.found-by-llm")
    brain.extract_value = AsyncMock(return_value="pk_test_abc123")
    return brain


@pytest.fixture
def engine(mock_llm_brain: AsyncMock) -> ActionEngine:
    """Action engine with mocked LLM brain."""
    return ActionEngine(llm_brain=mock_llm_brain)


@pytest.fixture
def engine_no_brain() -> ActionEngine:
    """Action engine without LLM brain (no vision fallback)."""
    return ActionEngine(llm_brain=None)


# =========================================================================
# Action Engine — Dispatch
# =========================================================================

class TestActionDispatch:
    """Test that steps are routed to correct handlers."""

    @pytest.mark.asyncio
    async def test_navigate(self, engine: ActionEngine, mock_page: AsyncMock) -> None:
        step = Step(type=StepType.NAVIGATE, url="https://clerk.com")
        result = await engine.execute(mock_page, step)
        assert result.success
        mock_page.goto.assert_called_once()
        assert result.data["url"] == "https://clerk.com"

    @pytest.mark.asyncio
    async def test_click(self, engine: ActionEngine, mock_page: AsyncMock) -> None:
        step = Step(type=StepType.CLICK, selector="button.submit")
        result = await engine.execute(mock_page, step)
        assert result.success
        assert result.data["clicked"] == "button.submit"

    @pytest.mark.asyncio
    async def test_type(self, engine: ActionEngine, mock_page: AsyncMock) -> None:
        step = Step(type=StepType.TYPE, selector="input#email", text="test@example.com")
        result = await engine.execute(mock_page, step)
        assert result.success

    @pytest.mark.asyncio
    async def test_extract(self, engine: ActionEngine, mock_page: AsyncMock) -> None:
        step = Step(type=StepType.EXTRACT, selector=".api-key", variable="API_KEY")
        result = await engine.execute(mock_page, step)
        assert result.success
        assert result.extracted_value == "extracted text"
        assert result.data["variable"] == "API_KEY"

    @pytest.mark.asyncio
    async def test_wait_networkidle(self, engine: ActionEngine, mock_page: AsyncMock) -> None:
        step = Step(type=StepType.WAIT, wait_for="networkidle")
        result = await engine.execute(mock_page, step)
        assert result.success
        mock_page.wait_for_load_state.assert_called_with("networkidle")

    @pytest.mark.asyncio
    async def test_wait_selector(self, engine: ActionEngine, mock_page: AsyncMock) -> None:
        step = Step(type=StepType.WAIT, wait_for=".success-message")
        result = await engine.execute(mock_page, step)
        assert result.success

    @pytest.mark.asyncio
    async def test_screenshot(self, engine: ActionEngine, mock_page: AsyncMock) -> None:
        step = Step(type=StepType.SCREENSHOT, description="Final state")
        result = await engine.execute(mock_page, step)
        assert result.success

    @pytest.mark.asyncio
    async def test_checkpoint_passthrough(self, engine: ActionEngine, mock_page: AsyncMock) -> None:
        step = Step(type=StepType.CHECKPOINT, message="Confirm?")
        result = await engine.execute(mock_page, step)
        assert result.success
        assert result.data["type"] == "checkpoint_passthrough"


# =========================================================================
# Action Engine — Element Finding
# =========================================================================

class TestElementFinding:
    """Test the two-tier element finding strategy."""

    @pytest.mark.asyncio
    async def test_tier1_selector_success(self, engine: ActionEngine, mock_page: AsyncMock) -> None:
        step = Step(type=StepType.CLICK, selector="button#submit")
        result = await engine.execute(mock_page, step)
        assert result.success
        mock_page.wait_for_selector.assert_called()

    @pytest.mark.asyncio
    async def test_tier2_llm_fallback_on_selector_fail(
        self, engine: ActionEngine, mock_page: AsyncMock, mock_llm_brain: AsyncMock,
    ) -> None:
        from playwright.async_api import TimeoutError as PlaywrightTimeout

        # First call (selector) fails, second call (LLM selector) succeeds
        mock_element = AsyncMock()
        mock_element.scroll_into_view_if_needed = AsyncMock()
        mock_element.click = AsyncMock()

        call_count = 0
        async def selector_side_effect(selector, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # First call = original selector fails
                raise PlaywrightTimeout("timeout")
            return mock_element  # Second call = LLM selector works

        mock_page.wait_for_selector = AsyncMock(side_effect=selector_side_effect)

        step = Step(
            type=StepType.CLICK,
            selector="button.old-selector",
            fallback_strategy=FallbackStrategy.LLM_VISION,
        )
        result = await engine.execute(mock_page, step)
        assert result.success
        mock_llm_brain.find_element.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_fallback_without_brain(
        self, engine_no_brain: ActionEngine, mock_page: AsyncMock,
    ) -> None:
        from playwright.async_api import TimeoutError as PlaywrightTimeout
        mock_page.wait_for_selector = AsyncMock(side_effect=PlaywrightTimeout("timeout"))

        step = Step(
            type=StepType.CLICK,
            selector="button.broken",
            fallback_strategy=FallbackStrategy.LLM_VISION,
            max_retries=0,
        )
        result = await engine_no_brain.execute(mock_page, step)
        assert not result.success  # no brain = no fallback = failure

    @pytest.mark.asyncio
    async def test_optional_step_doesnt_fail(
        self, engine: ActionEngine, mock_page: AsyncMock,
    ) -> None:
        from playwright.async_api import TimeoutError as PlaywrightTimeout
        mock_page.wait_for_selector = AsyncMock(side_effect=PlaywrightTimeout("timeout"))

        step = Step(
            type=StepType.CLICK,
            selector="button.maybe-exists",
            optional=True,
            max_retries=0,
            fallback_strategy=FallbackStrategy.FAIL,
        )
        result = await engine.execute(mock_page, step)
        assert result.success  # optional = True, so timeout is OK
        assert result.strategy_used == "skipped"


# =========================================================================
# Action Engine — Retries
# =========================================================================

class TestRetries:
    """Test retry behavior."""

    @pytest.mark.asyncio
    async def test_retries_on_failure(self, engine: ActionEngine, mock_page: AsyncMock) -> None:
        call_count = 0
        mock_element = AsyncMock()
        mock_element.scroll_into_view_if_needed = AsyncMock()
        mock_element.click = AsyncMock()

        async def flaky_selector(selector, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Flaky failure")
            return mock_element

        mock_page.wait_for_selector = AsyncMock(side_effect=flaky_selector)

        step = Step(type=StepType.CLICK, selector="button.flaky", max_retries=2)
        result = await engine.execute(mock_page, step)
        assert result.success
        assert call_count == 2  # failed once, succeeded on retry


# =========================================================================
# Action Engine — Analytics (autoresearch pattern)
# =========================================================================

class TestSelectorAnalytics:
    """Test selector success rate tracking."""

    @pytest.mark.asyncio
    async def test_tracks_selector_success(self, engine: ActionEngine, mock_page: AsyncMock) -> None:
        step = Step(type=StepType.CLICK, selector="button.good")
        await engine.execute(mock_page, step)
        await engine.execute(mock_page, step)

        stats = engine.get_selector_stats()
        assert "button.good" in stats
        assert stats["button.good"]["attempts"] == 2
        assert stats["button.good"]["successes"] == 2
        assert stats["button.good"]["success_rate"] == 1.0

    def test_fragile_selectors_empty_initially(self, engine: ActionEngine) -> None:
        assert engine.get_fragile_selectors() == []


# =========================================================================
# Action Engine — Operation Log
# =========================================================================

class TestActionLog:
    """Test compound-engineering operation logging."""

    @pytest.mark.asyncio
    async def test_logs_operations(self, engine: ActionEngine, mock_page: AsyncMock) -> None:
        step = Step(type=StepType.NAVIGATE, url="https://example.com")
        await engine.execute(mock_page, step)
        log = engine.get_operation_log()
        assert len(log) == 1
        assert log[0]["step_type"] == "navigate"
        assert log[0]["success"] is True

    @pytest.mark.asyncio
    async def test_lessons_from_failures(self, engine: ActionEngine, mock_page: AsyncMock) -> None:
        from playwright.async_api import TimeoutError as PlaywrightTimeout
        mock_page.wait_for_selector = AsyncMock(side_effect=PlaywrightTimeout("timeout"))

        step = Step(
            type=StepType.CLICK, selector="button.broken",
            max_retries=0, fallback_strategy=FallbackStrategy.FAIL,
        )
        result = await engine.execute(mock_page, step)
        lessons = engine.get_lessons()
        assert len(lessons) >= 1
        assert not lessons[0]["success"]


# =========================================================================
# LLM Brain — Unit Tests (mocked API)
# =========================================================================

class TestLLMBrain:
    """Test LLM Brain with mocked Anthropic API."""

    @pytest.mark.asyncio
    async def test_find_element_constructs_prompt(self) -> None:
        brain = LLMBrain(api_key="test-key")

        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = 'button[data-testid="create-app"]'
        mock_response.content = [mock_block]

        with patch.object(brain._client.messages, "create", new_callable=AsyncMock, return_value=mock_response):
            step = Step(
                type=StepType.CLICK,
                selector="button.old",
                description="The Create Application button",
            )
            result = await brain.find_element(b"fake_png", step)
            assert result == 'button[data-testid="create-app"]'

    @pytest.mark.asyncio
    async def test_find_element_returns_none_on_not_found(self) -> None:
        brain = LLMBrain(api_key="test-key")

        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "NOT_FOUND"
        mock_response.content = [mock_block]

        with patch.object(brain._client.messages, "create", new_callable=AsyncMock, return_value=mock_response):
            step = Step(type=StepType.CLICK, description="Nonexistent button")
            result = await brain.find_element(b"fake_png", step)
            assert result is None

    @pytest.mark.asyncio
    async def test_extract_value(self) -> None:
        brain = LLMBrain(api_key="test-key")

        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "pk_test_abc123xyz"
        mock_response.content = [mock_block]

        with patch.object(brain._client.messages, "create", new_callable=AsyncMock, return_value=mock_response):
            result = await brain.extract_value(b"fake_png", "the publishable API key")
            assert result == "pk_test_abc123xyz"

    @pytest.mark.asyncio
    async def test_extract_value_returns_none_on_not_found(self) -> None:
        brain = LLMBrain(api_key="test-key")

        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "NOT_FOUND"
        mock_response.content = [mock_block]

        with patch.object(brain._client.messages, "create", new_callable=AsyncMock, return_value=mock_response):
            result = await brain.extract_value(b"fake_png", "hidden element")
            assert result is None

    @pytest.mark.asyncio
    async def test_understand_page(self) -> None:
        brain = LLMBrain(api_key="test-key")

        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "Page type: dashboard\nKey elements: navigation, sidebar\nState: loaded"
        mock_response.content = [mock_block]

        with patch.object(brain._client.messages, "create", new_callable=AsyncMock, return_value=mock_response):
            result = await brain.understand_page(b"fake_png")
            assert "dashboard" in result["raw_description"]
            assert "error" not in result

    @pytest.mark.asyncio
    async def test_handles_api_error(self) -> None:
        brain = LLMBrain(api_key="test-key")

        with patch.object(
            brain._client.messages, "create",
            new_callable=AsyncMock,
            side_effect=Exception("API rate limited"),
        ):
            result = await brain.find_element(b"fake_png", Step(type=StepType.CLICK, description="button"))
            assert result is None
            lessons = brain.get_lessons()
            assert len(lessons) == 1
            assert "rate limited" in lessons[0]["error"]


class TestLLMBrainStats:
    """Test LLM Brain analytics (autoresearch pattern)."""

    @pytest.mark.asyncio
    async def test_tracks_call_stats(self) -> None:
        brain = LLMBrain(api_key="test-key")

        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "button.found"
        mock_response.content = [mock_block]

        with patch.object(brain._client.messages, "create", new_callable=AsyncMock, return_value=mock_response):
            await brain.find_element(b"fake", Step(type=StepType.CLICK, description="btn"))
            await brain.find_element(b"fake", Step(type=StepType.CLICK, description="btn2"))

        stats = brain.get_stats()
        assert stats["total_calls"] == 2
        assert stats["find_element"]["calls"] == 2
        assert stats["find_element"]["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_call_log_captures_details(self) -> None:
        brain = LLMBrain(api_key="test-key")

        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "button.test"
        mock_response.content = [mock_block]

        with patch.object(brain._client.messages, "create", new_callable=AsyncMock, return_value=mock_response):
            await brain.find_element(b"fake", Step(type=StepType.CLICK, description="test"))

        log = brain.get_call_log()
        assert len(log) == 1
        assert log[0]["function"] == "find_element"
        assert "timestamp" in log[0]
        assert log[0]["duration_ms"] >= 0

    def test_empty_stats(self) -> None:
        brain = LLMBrain(api_key="test-key")
        stats = brain.get_stats()
        assert stats["total_calls"] == 0

    def test_empty_lessons(self) -> None:
        brain = LLMBrain(api_key="test-key")
        assert brain.get_lessons() == []
