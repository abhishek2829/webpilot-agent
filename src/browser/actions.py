"""WebPilot Agent — Action Engine.

Executes individual browser steps: click, type, extract, wait, select, scroll.
Uses a two-tier element finding strategy:
  Tier 1: CSS/XPath selector (fast, deterministic)
  Tier 2: LLM vision fallback (adaptive, handles website changes)

Analogy: If the Browser Session is the agent's body, the Action Engine
is its muscle memory — it knows HOW to click a button, type in a field,
or copy text from a page. The LLM Brain (Task 7) is what it calls when
muscle memory fails and it needs to "look" at the page to figure things out.

Patterns applied:
- playwright-skill: selector strategies, wait patterns, form filling
- GSD verification: every action verified after execution
- compound-engineering: failures captured with context for self-improvement
- autoresearch: selector success/fail rates tracked per-step
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from playwright.async_api import Page, ElementHandle, TimeoutError as PlaywrightTimeout

from src.core.models import Step, StepType, FallbackStrategy

logger = logging.getLogger(__name__)


class ActionError(Exception):
    """Raised when a browser action fails after all retry/fallback attempts."""

    def __init__(self, step: Step, message: str, screenshot: bytes | None = None) -> None:
        self.step = step
        self.screenshot = screenshot
        super().__init__(message)


class ElementNotFoundError(ActionError):
    """Raised when an element cannot be located by any strategy."""
    pass


class ActionResult:
    """The outcome of executing a single step."""

    def __init__(
        self,
        success: bool,
        data: dict[str, Any] | None = None,
        extracted_value: str | None = None,
        duration_ms: int = 0,
        strategy_used: str = "selector",
        error: str | None = None,
    ) -> None:
        self.success = success
        self.data = data or {}
        self.extracted_value = extracted_value
        self.duration_ms = duration_ms
        self.strategy_used = strategy_used
        self.error = error


class ActionEngine:
    """Executes browser actions for each step in a workflow.

    The engine handles the two-tier element finding:
    1. Try the CSS/XPath selector directly (fast path)
    2. If that fails and fallback_strategy is "llm_vision", ask the LLM brain
       to find the element by looking at a screenshot

    The LLM brain is injected as a dependency — the action engine doesn't
    know about Claude directly. It just calls llm_brain.find_element().

    Usage:
        engine = ActionEngine(llm_brain=my_brain)
        result = await engine.execute(page, step)
    """

    def __init__(self, llm_brain: Any = None) -> None:
        """
        Args:
            llm_brain: Object with async find_element(screenshot, step) method.
                      Returns a CSS selector string. None = no vision fallback.
        """
        self._llm_brain = llm_brain
        self._operation_log: list[dict] = []

        # Autoresearch pattern: track selector success rates
        self._selector_stats: dict[str, dict] = {}

    # =========================================================================
    # Main Dispatcher
    # =========================================================================

    async def execute(self, page: Page, step: Step) -> ActionResult:
        """Execute a single browser action step.

        This is the main entry point. Dispatches to the appropriate handler
        based on step.type, handles retries and fallbacks.

        Args:
            page: The Playwright page to act on
            step: The Step model defining what to do

        Returns:
            ActionResult with success/failure, extracted data, timing
        """
        start = time.monotonic()

        for attempt in range(step.max_retries + 1):
            try:
                result = await self._dispatch(page, step)
                result.duration_ms = int((time.monotonic() - start) * 1000)
                self._log_op(step, result, attempt=attempt)
                return result

            except PlaywrightTimeout:
                if attempt < step.max_retries:
                    logger.warning(
                        "Step %s timed out (attempt %d/%d), retrying...",
                        step.type.value, attempt + 1, step.max_retries + 1,
                    )
                    continue

                # Final attempt failed — try LLM vision fallback
                if step.fallback_strategy == FallbackStrategy.LLM_VISION and self._llm_brain:
                    try:
                        result = await self._vision_fallback(page, step)
                        result.duration_ms = int((time.monotonic() - start) * 1000)
                        self._log_op(step, result, attempt=attempt, fallback=True)
                        return result
                    except Exception as vision_err:
                        logger.error("Vision fallback also failed: %s", vision_err)

                if step.optional:
                    return ActionResult(
                        success=True,
                        strategy_used="skipped",
                        data={"reason": "optional step timed out"},
                        duration_ms=int((time.monotonic() - start) * 1000),
                    )

                duration = int((time.monotonic() - start) * 1000)
                error_result = ActionResult(
                    success=False, error=f"Timeout after {step.max_retries + 1} attempts",
                    duration_ms=duration,
                )
                self._log_op(step, error_result, attempt=attempt)
                return error_result

            except Exception as e:
                if attempt < step.max_retries:
                    logger.warning("Step %s failed: %s, retrying...", step.type.value, e)
                    continue

                if step.optional:
                    return ActionResult(
                        success=True, strategy_used="skipped",
                        data={"reason": f"optional step failed: {e}"},
                        duration_ms=int((time.monotonic() - start) * 1000),
                    )

                duration = int((time.monotonic() - start) * 1000)
                error_result = ActionResult(
                    success=False, error=str(e), duration_ms=duration,
                )
                self._log_op(step, error_result, attempt=attempt)
                return error_result

    async def _dispatch(self, page: Page, step: Step) -> ActionResult:
        """Route step to the correct handler based on type."""
        match step.type:
            case StepType.NAVIGATE:
                return await self._navigate(page, step)
            case StepType.CLICK:
                return await self._click(page, step)
            case StepType.TYPE:
                return await self._type(page, step)
            case StepType.EXTRACT:
                return await self._extract(page, step)
            case StepType.WAIT:
                return await self._wait(page, step)
            case StepType.SELECT:
                return await self._select(page, step)
            case StepType.SCROLL:
                return await self._scroll(page, step)
            case StepType.SCREENSHOT:
                return await self._screenshot(page, step)
            case StepType.CHECKPOINT:
                # Checkpoints are handled by CheckpointManager, not ActionEngine
                return ActionResult(success=True, data={"type": "checkpoint_passthrough"})
            case _:
                return ActionResult(success=False, error=f"Unknown step type: {step.type}")

    # =========================================================================
    # Action Handlers
    # =========================================================================

    async def _navigate(self, page: Page, step: Step) -> ActionResult:
        """Navigate to a URL."""
        assert step.url, "NAVIGATE step requires url"
        await page.goto(step.url, wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle")
        title = await page.title()
        return ActionResult(
            success=True,
            data={"url": step.url, "title": title, "final_url": page.url},
        )

    async def _click(self, page: Page, step: Step) -> ActionResult:
        """Click an element."""
        element = await self._find_element(page, step)
        await element.scroll_into_view_if_needed()
        await element.click()
        # Brief wait for any navigation or DOM update
        await page.wait_for_timeout(500)
        return ActionResult(success=True, data={"clicked": step.selector or step.description})

    async def _type(self, page: Page, step: Step) -> ActionResult:
        """Type text into an input field."""
        assert step.text is not None, "TYPE step requires text"
        element = await self._find_element(page, step)
        # Clear existing content first, then type
        await element.click()
        await element.fill("")
        await element.fill(step.text)
        return ActionResult(
            success=True,
            data={"typed": step.text[:50] + ("..." if len(step.text) > 50 else "")},
        )

    async def _extract(self, page: Page, step: Step) -> ActionResult:
        """Extract a value from the page."""
        element = await self._find_element(page, step)

        match step.extract_attribute:
            case "textContent":
                value = await element.text_content() or ""
            case "value":
                value = await element.input_value() if await element.is_visible() else ""
            case _:
                value = await element.get_attribute(step.extract_attribute) or ""

        value = value.strip()

        return ActionResult(
            success=True,
            extracted_value=value,
            data={"variable": step.variable, "value": value[:100]},
        )

    async def _wait(self, page: Page, step: Step) -> ActionResult:
        """Wait for a condition."""
        if step.wait_for == "networkidle":
            await page.wait_for_load_state("networkidle")
        elif step.wait_for:
            await page.wait_for_selector(
                step.wait_for, timeout=step.timeout_seconds * 1000,
            )
        else:
            await page.wait_for_timeout(step.timeout_seconds * 1000)

        return ActionResult(success=True, data={"waited_for": step.wait_for or "timeout"})

    async def _select(self, page: Page, step: Step) -> ActionResult:
        """Select an option from a dropdown."""
        assert step.text, "SELECT step requires text (the option to select)"
        element = await self._find_element(page, step)
        await element.select_option(label=step.text)
        return ActionResult(success=True, data={"selected": step.text})

    async def _scroll(self, page: Page, step: Step) -> ActionResult:
        """Scroll to an element or position."""
        if step.selector:
            element = await self._find_element(page, step)
            await element.scroll_into_view_if_needed()
        else:
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
        return ActionResult(success=True, data={"scrolled": step.selector or "page_down"})

    async def _screenshot(self, page: Page, step: Step) -> ActionResult:
        """Take a screenshot (without checkpoint)."""
        screenshot = await page.screenshot(full_page=True, type="png")
        return ActionResult(
            success=True,
            data={"screenshot_bytes": len(screenshot), "description": step.description},
        )

    # =========================================================================
    # Two-Tier Element Finding
    # =========================================================================

    async def _find_element(self, page: Page, step: Step) -> ElementHandle:
        """Find an element using the two-tier strategy.

        Tier 1: Direct CSS/XPath selector (fast, ~5ms)
        Tier 2: LLM vision fallback (adaptive, ~2-5s)

        The selector might be:
        - CSS: "button.submit", "#email-input"
        - Text-based: "button:has-text('Create')"
        - XPath: "//button[@data-testid='submit']"
        - Compound: "input[name='name'], input[placeholder*='name' i]"
        """
        # Tier 1: Try CSS selector(s)
        if step.selector:
            # Handle comma-separated selectors (try each)
            selectors = [s.strip() for s in step.selector.split(",")]
            for selector in selectors:
                try:
                    element = await page.wait_for_selector(
                        selector, timeout=5000, state="visible",
                    )
                    if element:
                        self._track_selector(step.selector, success=True)
                        return element
                except (PlaywrightTimeout, Exception):
                    continue

            self._track_selector(step.selector, success=False)

        # Tier 2: LLM vision fallback
        if step.fallback_strategy == FallbackStrategy.LLM_VISION and self._llm_brain:
            logger.info(
                "Selector failed for '%s', falling back to LLM vision",
                step.description or step.selector,
            )
            screenshot = await page.screenshot(full_page=False, type="png")
            llm_selector = await self._llm_brain.find_element(screenshot, step)

            if llm_selector:
                try:
                    element = await page.wait_for_selector(
                        llm_selector, timeout=5000, state="visible",
                    )
                    if element:
                        logger.info("LLM vision found element: %s", llm_selector)
                        return element
                except (PlaywrightTimeout, Exception) as e:
                    logger.warning("LLM-suggested selector failed: %s -> %s", llm_selector, e)

        # All strategies exhausted
        raise ElementNotFoundError(
            step=step,
            message=(
                f"Could not find element: "
                f"selector='{step.selector}', description='{step.description}'"
            ),
        )

    async def _vision_fallback(self, page: Page, step: Step) -> ActionResult:
        """Full vision-based execution — LLM sees the page and acts."""
        if not self._llm_brain:
            return ActionResult(success=False, error="No LLM brain configured for vision fallback")

        screenshot = await page.screenshot(full_page=False, type="png")
        llm_selector = await self._llm_brain.find_element(screenshot, step)

        if llm_selector:
            element = await page.wait_for_selector(llm_selector, timeout=10000)
            if element:
                match step.type:
                    case StepType.CLICK:
                        await element.click()
                    case StepType.TYPE:
                        await element.fill(step.text or "")
                    case StepType.EXTRACT:
                        value = await element.text_content() or ""
                        return ActionResult(
                            success=True, extracted_value=value.strip(),
                            strategy_used="llm_vision",
                        )
                return ActionResult(success=True, strategy_used="llm_vision")

        return ActionResult(success=False, error="LLM vision could not find element")

    # =========================================================================
    # Selector Analytics (autoresearch pattern)
    # =========================================================================

    def _track_selector(self, selector: str, success: bool) -> None:
        """Track selector success/failure rates.

        Over time, this data reveals which selectors are fragile
        (frequently fail) vs. reliable. Feed into self-learning agent
        to suggest better selectors for workflow YAML files.
        """
        if selector not in self._selector_stats:
            self._selector_stats[selector] = {"attempts": 0, "successes": 0}
        self._selector_stats[selector]["attempts"] += 1
        if success:
            self._selector_stats[selector]["successes"] += 1

    def get_selector_stats(self) -> dict[str, dict]:
        """Return selector reliability data for the self-improvement loop."""
        return {
            selector: {
                **stats,
                "success_rate": (
                    stats["successes"] / stats["attempts"]
                    if stats["attempts"] > 0
                    else 0.0
                ),
            }
            for selector, stats in self._selector_stats.items()
        }

    def get_fragile_selectors(self, threshold: float = 0.5) -> list[dict]:
        """Return selectors with success rate below threshold.

        These are candidates for improvement — either rewrite the selector
        or switch to a description-based approach with LLM vision.
        """
        stats = self.get_selector_stats()
        return [
            {"selector": sel, **data}
            for sel, data in stats.items()
            if data["success_rate"] < threshold and data["attempts"] >= 3
        ]

    # =========================================================================
    # Compound Engineering: Operation Log
    # =========================================================================

    def _log_op(
        self, step: Step, result: ActionResult, attempt: int = 0, fallback: bool = False,
    ) -> None:
        """Track every action for the error→lesson loop."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step_type": step.type.value,
            "selector": step.selector,
            "description": step.description,
            "success": result.success,
            "strategy": result.strategy_used,
            "attempt": attempt,
            "fallback_used": fallback,
            "duration_ms": result.duration_ms,
            "error": result.error,
        }
        self._operation_log.append(entry)
        if len(self._operation_log) > 500:
            self._operation_log = self._operation_log[-500:]

    def get_operation_log(self) -> list[dict]:
        return list(self._operation_log)

    def get_lessons(self) -> list[dict]:
        return [op for op in self._operation_log if not op.get("success", True)]
