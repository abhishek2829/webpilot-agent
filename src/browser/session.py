"""WebPilot Agent — Browser Session Manager.

Manages the Playwright browser lifecycle: launch, context creation,
screenshot capture, session state persistence, and cleanup.

Analogy: This is the agent's "body" — the physical browser it controls.
Just like a human opens Chrome, logs in, and their cookies persist,
the session manager handles all of that for the agent.

Patterns applied:
- playwright-skill: headless/headed modes, slowMo for debugging
- compound-engineering: every browser operation logged for lessons
- GSD checkpoint: session state can be paused and resumed
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

logger = logging.getLogger(__name__)


class BrowserSessionError(Exception):
    """Browser session lifecycle errors."""
    pass


class BrowserSession:
    """Manages a single Playwright browser session.

    Lifecycle:
        session = BrowserSession(config)
        await session.start()
        page = session.page

        # ... do work ...
        screenshot = await session.screenshot()

        # Save state for resumption
        await session.save_state()

        # Later: restore
        await session.start()  # auto-loads saved state

        await session.close()

    Thread safety: One session = one browser context. Don't share across tasks.
    """

    def __init__(
        self,
        headless: bool = False,
        slow_mo: int = 100,
        timeout: int = 30000,
        screenshot_dir: Path = Path("./data/screenshots"),
        state_path: Path | None = None,
        viewport_width: int = 1280,
        viewport_height: int = 800,
    ) -> None:
        self._headless = headless
        self._slow_mo = slow_mo
        self._timeout = timeout
        self._screenshot_dir = screenshot_dir
        self._state_path = state_path or Path("./data/browser_state.json")
        self._viewport = {"width": viewport_width, "height": viewport_height}

        self._screenshot_dir.mkdir(parents=True, exist_ok=True)

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._started = False

        # Compound-engineering: operation tracking
        self._operation_log: list[dict] = []
        self._screenshot_count = 0

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def start(self) -> None:
        """Launch browser and create a fresh context.

        If a saved state exists (cookies, localStorage), it's restored
        automatically — so the agent stays "logged in" between runs.
        """
        if self._started:
            logger.warning("Session already started — close first")
            return

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
            slow_mo=self._slow_mo,
        )

        # Restore saved state if available (cookies, localStorage)
        storage_state = None
        if self._state_path.exists():
            try:
                storage_state = str(self._state_path)
                logger.info("Restoring browser state from %s", self._state_path)
            except Exception as e:
                logger.warning("Failed to load browser state: %s", e)
                storage_state = None

        self._context = await self._browser.new_context(
            viewport=self._viewport,
            storage_state=storage_state,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )

        self._context.set_default_timeout(self._timeout)
        self._page = await self._context.new_page()
        self._started = True
        self._log_op("start", success=True)
        logger.info(
            "Browser session started (headless=%s, slowMo=%d)",
            self._headless, self._slow_mo,
        )

    async def close(self) -> None:
        """Close browser and clean up all resources."""
        if not self._started:
            return

        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning("Error during browser cleanup: %s", e)
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            self._started = False
            self._log_op("close", success=True)

    async def __aenter__(self) -> BrowserSession:
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # =========================================================================
    # State Persistence (GSD checkpoint pattern — pause/resume)
    # =========================================================================

    async def save_state(self) -> Path:
        """Save browser state (cookies, localStorage) for later resumption.

        This is the GSD checkpoint pattern: the agent can pause mid-workflow,
        save its logged-in state, and resume later without re-authenticating.
        """
        self._ensure_started()
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        await self._context.storage_state(path=str(self._state_path))
        self._log_op("save_state", success=True)
        logger.info("Browser state saved to %s", self._state_path)
        return self._state_path

    def has_saved_state(self) -> bool:
        """Check if a saved browser state exists."""
        return self._state_path.exists()

    def clear_saved_state(self) -> None:
        """Delete saved browser state."""
        if self._state_path.exists():
            self._state_path.unlink()
            logger.info("Saved browser state cleared")

    # =========================================================================
    # Page Access
    # =========================================================================

    @property
    def page(self) -> Page:
        """The active Playwright page. Use this for all browser interactions."""
        self._ensure_started()
        assert self._page is not None
        return self._page

    @property
    def context(self) -> BrowserContext:
        """The browser context (for multi-tab scenarios)."""
        self._ensure_started()
        assert self._context is not None
        return self._context

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def current_url(self) -> str:
        """Current page URL."""
        if self._page:
            return self._page.url
        return ""

    @property
    def current_title(self) -> str | None:
        """Current page title (None if page not loaded)."""
        # Title requires async, return None for sync access
        return None

    # =========================================================================
    # Navigation
    # =========================================================================

    async def goto(self, url: str, wait_until: str = "domcontentloaded") -> None:
        """Navigate to a URL.

        Args:
            url: The URL to navigate to
            wait_until: When to consider navigation done.
                       Options: "domcontentloaded", "load", "networkidle"
        """
        self._ensure_started()
        try:
            await self._page.goto(url, wait_until=wait_until)
            self._log_op("goto", success=True, url=url)
            logger.info("Navigated to: %s", url)
        except Exception as e:
            self._log_op("goto", success=False, url=url, error=str(e))
            raise BrowserSessionError(f"Failed to navigate to {url}: {e}") from e

    async def wait_for_load(self, state: str = "networkidle") -> None:
        """Wait for page to reach a load state.

        Args:
            state: "networkidle", "domcontentloaded", or "load"
        """
        self._ensure_started()
        await self._page.wait_for_load_state(state)

    # =========================================================================
    # Screenshots
    # =========================================================================

    async def screenshot(
        self,
        full_page: bool = True,
        label: str = "",
    ) -> bytes:
        """Take a screenshot and return raw bytes.

        Args:
            full_page: Capture entire scrollable page (True) or viewport only (False)
            label: Optional label for the screenshot filename

        Returns:
            PNG image bytes
        """
        self._ensure_started()
        self._screenshot_count += 1

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        suffix = f"_{label}" if label else ""
        filename = f"screenshot_{timestamp}_{self._screenshot_count:03d}{suffix}.png"
        path = self._screenshot_dir / filename

        screenshot_bytes = await self._page.screenshot(
            full_page=full_page,
            path=str(path),
            type="png",
        )

        self._log_op("screenshot", success=True, path=str(path))
        logger.debug("Screenshot saved: %s", path)
        return screenshot_bytes

    async def screenshot_base64(
        self,
        full_page: bool = True,
        label: str = "",
    ) -> str:
        """Take a screenshot and return as base64 string.

        Ready to send to Claude's vision API.
        """
        raw = await self.screenshot(full_page=full_page, label=label)
        return base64.b64encode(raw).decode()

    # =========================================================================
    # Page Info
    # =========================================================================

    async def get_title(self) -> str:
        """Get the current page title."""
        self._ensure_started()
        return await self._page.title()

    async def get_text_content(self) -> str:
        """Get all visible text on the page.

        Useful for LLM to understand page context without a screenshot.
        """
        self._ensure_started()
        return await self._page.inner_text("body")

    async def get_accessibility_tree(self) -> dict:
        """Get the page's accessibility tree (a11y snapshot).

        This is the structured representation the LLM can use to understand
        page layout and find elements by role/name without CSS selectors.
        """
        self._ensure_started()
        snapshot = await self._page.accessibility.snapshot()
        return snapshot or {}

    # =========================================================================
    # Compound Engineering: Operation Logging
    # =========================================================================

    def _log_op(self, operation: str, success: bool, **extra: Any) -> None:
        """Track browser operations for the error→lesson feedback loop."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            "success": success,
            "url": self.current_url if self._started else "",
            **{k: v for k, v in extra.items() if k != "url" or "url" not in extra},
            **extra,
        }
        self._operation_log.append(entry)
        if len(self._operation_log) > 200:
            self._operation_log = self._operation_log[-200:]

    def get_operation_log(self) -> list[dict]:
        """Full operation history for observability."""
        return list(self._operation_log)

    def get_lessons(self) -> list[dict]:
        """Failed operations — compound-engineering lessons."""
        return [op for op in self._operation_log if not op.get("success", True)]

    # =========================================================================
    # Internal
    # =========================================================================

    def _ensure_started(self) -> None:
        """Guard: raise if session not started."""
        if not self._started or self._page is None:
            raise BrowserSessionError(
                "Browser session not started. Call await session.start() first."
            )

    # =========================================================================
    # Factory
    # =========================================================================

    @classmethod
    def from_settings(cls, settings) -> BrowserSession:
        """Create from application settings."""
        return cls(
            headless=settings.browser_headless,
            slow_mo=settings.browser_slow_mo,
            timeout=settings.browser_timeout,
            screenshot_dir=settings.screenshot_dir,
            state_path=settings.screenshot_dir.parent / "browser_state.json",
        )
