"""WebPilot Agent — LLM Brain (Claude Vision Integration).

The "brain" of the agent — uses Claude's vision capabilities to:
1. Find elements on a page when CSS selectors fail
2. Extract values from screenshots when DOM extraction fails
3. Understand page context to make decisions

Analogy: The Action Engine is the agent's muscle memory (knows how to click).
The LLM Brain is its visual cortex — it "looks" at the page and figures out
where to click when muscle memory fails. Like a human squinting at a
redesigned website: "ah, they moved the Sign Up button to the top right."

Patterns applied:
- compound-engineering: every LLM call logged with prompt/response for lessons
- autoresearch: track which prompts work best → improve over time
- awesome-ai-system-prompts: informed prompt engineering
"""

from __future__ import annotations

import base64
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from anthropic import AsyncAnthropic

from src.core.models import Step

logger = logging.getLogger(__name__)


class LLMBrainError(Exception):
    """Raised when LLM vision fails."""
    pass


class LLMBrain:
    """Claude-powered vision and reasoning for the browser agent.

    Two primary functions:
    1. find_element(screenshot, step) → CSS selector string
    2. extract_value(screenshot, description) → extracted text

    Both use Claude's vision API: send a screenshot + instruction,
    get back structured output.

    Usage:
        brain = LLMBrain(api_key="sk-ant-...")
        selector = await brain.find_element(screenshot_bytes, step)
        value = await brain.extract_value(screenshot_bytes, "the API key")
    """

    # System prompts — refined for browser agent tasks
    FIND_ELEMENT_SYSTEM = """You are a browser automation assistant. You are looking at a screenshot of a web page.

Your task: Find a specific element on the page and return a CSS selector that uniquely identifies it.

Rules:
- Return ONLY a valid CSS selector string, nothing else
- Prefer specific selectors: [data-testid], [aria-label], [name], [id]
- Use text-based selectors when needed: button:has-text('Create'), a:has-text('Sign up')
- If the element has a role, use role selectors: [role="button"]
- For inputs, prefer: input[name="..."] or input[placeholder="..."]
- If multiple elements match, add parent context: .modal input[name="email"]
- Return "NOT_FOUND" if the element is genuinely not visible on the page
- Do NOT return XPath — only CSS selectors
- Do NOT explain your reasoning — just the selector"""

    EXTRACT_VALUE_SYSTEM = """You are a browser automation assistant. You are looking at a screenshot of a web page.

Your task: Extract a specific text value from the page.

Rules:
- Return ONLY the extracted value, nothing else
- If the value looks like an API key (starts with pk_, sk_, etc.), return it exactly
- If the value is in a code block or monospace font, return just the text content
- Strip any surrounding whitespace or labels
- Return "NOT_FOUND" if the value is not visible on the page
- Do NOT explain your reasoning — just the value"""

    UNDERSTAND_PAGE_SYSTEM = """You are a browser automation assistant. You are looking at a screenshot of a web page.

Your task: Describe what you see on the page to help decide what action to take next.

Provide a brief structured response:
- Page type: (login, dashboard, form, error, confirmation, etc.)
- Key elements visible: (buttons, inputs, messages, navigation)
- Current state: (loaded, loading, error, requires action)
- Suggested next action: (what the automation should do next)"""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 500,
    ) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

        # Compound-engineering: log every LLM call
        self._call_log: list[dict] = []

    # =========================================================================
    # Core Functions
    # =========================================================================

    async def find_element(self, screenshot: bytes, step: Step) -> str | None:
        """Ask Claude to find an element on the page via screenshot.

        Args:
            screenshot: PNG image bytes of the current page
            step: The Step we're trying to execute (has description, selector)

        Returns:
            A CSS selector string, or None if element not found
        """
        prompt_parts = ["Find this element on the page:"]

        if step.description:
            prompt_parts.append(f"Description: {step.description}")
        if step.selector:
            prompt_parts.append(f"Original selector (failed): {step.selector}")
        if step.text:
            prompt_parts.append(f"Contains text: {step.text}")

        prompt = "\n".join(prompt_parts)
        start = time.monotonic()

        try:
            response = await self._vision_call(
                system=self.FIND_ELEMENT_SYSTEM,
                prompt=prompt,
                screenshot=screenshot,
            )

            duration_ms = int((time.monotonic() - start) * 1000)
            selector = response.strip().strip('"').strip("'").strip("`")

            self._log_call(
                function="find_element",
                prompt=prompt,
                response=selector,
                duration_ms=duration_ms,
                success=selector != "NOT_FOUND",
            )

            if selector == "NOT_FOUND" or not selector:
                logger.info("LLM Brain: element not found on page")
                return None

            logger.info("LLM Brain found selector: %s", selector)
            return selector

        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            self._log_call(
                function="find_element",
                prompt=prompt,
                response="",
                duration_ms=duration_ms,
                success=False,
                error=str(e),
            )
            logger.error("LLM Brain find_element failed: %s", e)
            return None

    async def extract_value(self, screenshot: bytes, description: str) -> str | None:
        """Ask Claude to read a value from the page screenshot.

        Used when DOM-based extraction fails — the value might be in
        a canvas, image, or dynamically rendered element.

        Args:
            screenshot: PNG image bytes
            description: What value to extract (e.g., "the publishable API key")

        Returns:
            The extracted value string, or None if not found
        """
        prompt = f"Extract this value from the page: {description}"
        start = time.monotonic()

        try:
            response = await self._vision_call(
                system=self.EXTRACT_VALUE_SYSTEM,
                prompt=prompt,
                screenshot=screenshot,
            )

            duration_ms = int((time.monotonic() - start) * 1000)
            value = response.strip()

            self._log_call(
                function="extract_value",
                prompt=prompt,
                response=value[:100],
                duration_ms=duration_ms,
                success=value != "NOT_FOUND",
            )

            if value == "NOT_FOUND" or not value:
                return None

            return value

        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            self._log_call(
                function="extract_value",
                prompt=prompt,
                response="",
                duration_ms=duration_ms,
                success=False,
                error=str(e),
            )
            logger.error("LLM Brain extract_value failed: %s", e)
            return None

    async def understand_page(self, screenshot: bytes) -> dict:
        """Ask Claude to describe the current page state.

        Useful for the Recovery Engine — when something unexpected happens,
        ask the brain "what am I looking at?" before deciding what to do.

        Returns:
            Dict with page_type, key_elements, current_state, suggested_action
        """
        prompt = "What do you see on this page? Describe the state and suggest next action."
        start = time.monotonic()

        try:
            response = await self._vision_call(
                system=self.UNDERSTAND_PAGE_SYSTEM,
                prompt=prompt,
                screenshot=screenshot,
            )

            duration_ms = int((time.monotonic() - start) * 1000)
            self._log_call(
                function="understand_page",
                prompt=prompt,
                response=response[:200],
                duration_ms=duration_ms,
                success=True,
            )

            return {"raw_description": response, "timestamp": datetime.now(timezone.utc).isoformat()}

        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            self._log_call(
                function="understand_page",
                prompt=prompt,
                response="",
                duration_ms=duration_ms,
                success=False,
                error=str(e),
            )
            return {"raw_description": f"Error: {e}", "error": True}

    # =========================================================================
    # Anthropic API Call
    # =========================================================================

    async def _vision_call(
        self, system: str, prompt: str, screenshot: bytes,
    ) -> str:
        """Make a vision API call to Claude.

        Sends a screenshot + text prompt and returns Claude's text response.
        """
        b64_image = base64.b64encode(screenshot).decode()

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64_image,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )

        # Extract text from response
        text_blocks = [
            block.text for block in response.content if hasattr(block, "text")
        ]
        return "\n".join(text_blocks).strip()

    # =========================================================================
    # Compound Engineering: Call Logging
    # =========================================================================

    def _log_call(
        self,
        function: str,
        prompt: str,
        response: str,
        duration_ms: int,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Track every LLM call for the self-improvement loop.

        This data feeds into the autoresearch pattern:
        - Which prompts consistently produce good selectors?
        - Which page types cause the most failures?
        - What's the average latency per call type?
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "function": function,
            "prompt": prompt[:200],
            "response": response[:200],
            "duration_ms": duration_ms,
            "success": success,
            "model": self._model,
        }
        if error:
            entry["error"] = error

        self._call_log.append(entry)
        if len(self._call_log) > 200:
            self._call_log = self._call_log[-200:]

    def get_call_log(self) -> list[dict]:
        """Full LLM call history for observability."""
        return list(self._call_log)

    def get_lessons(self) -> list[dict]:
        """Failed LLM calls — compound-engineering lessons."""
        return [call for call in self._call_log if not call.get("success", True)]

    def get_stats(self) -> dict:
        """LLM usage statistics.

        Returns call counts, success rates, and average latency per function.
        """
        if not self._call_log:
            return {"total_calls": 0}

        by_function: dict[str, list[dict]] = {}
        for call in self._call_log:
            fn = call.get("function", "unknown")
            by_function.setdefault(fn, []).append(call)

        stats = {"total_calls": len(self._call_log)}
        for fn, calls in by_function.items():
            successes = sum(1 for c in calls if c.get("success", False))
            durations = [c.get("duration_ms", 0) for c in calls]
            stats[fn] = {
                "calls": len(calls),
                "success_rate": successes / len(calls) if calls else 0,
                "avg_latency_ms": sum(durations) // len(durations) if durations else 0,
            }

        return stats

    # =========================================================================
    # Factory
    # =========================================================================

    @classmethod
    def from_settings(cls, settings) -> LLMBrain:
        """Create from application settings."""
        return cls(
            api_key=settings.anthropic_api_key,
            model=settings.llm_model,
            max_tokens=settings.llm_max_tokens,
        )
