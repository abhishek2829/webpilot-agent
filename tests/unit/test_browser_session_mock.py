"""Tests for Browser Session Manager using mocked Playwright (Task 17 coverage).

These tests mock Playwright's async API to test BrowserSession logic
without needing a real browser or SOCKS proxy.
"""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from src.browser.session import BrowserSession, BrowserSessionError


# =========================================================================
# Helpers: Mock Playwright objects
# =========================================================================

def _mock_playwright():
    """Create a mock playwright context manager."""
    pw = AsyncMock()
    browser = AsyncMock()
    context = AsyncMock()
    page = AsyncMock()

    pw.chromium.launch = AsyncMock(return_value=browser)
    browser.new_context = AsyncMock(return_value=context)
    context.new_page = AsyncMock(return_value=page)
    context.close = AsyncMock()
    context.storage_state = AsyncMock()
    browser.close = AsyncMock()
    pw.stop = AsyncMock()

    page.url = "about:blank"
    page.title = AsyncMock(return_value="Test Page")
    page.screenshot = AsyncMock(return_value=b"\x89PNG_test_bytes")
    page.inner_text = AsyncMock(return_value="Hello World")
    page.accessibility = MagicMock()
    page.accessibility.snapshot = AsyncMock(return_value={"role": "document"})
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()

    return pw, browser, context, page


@pytest.fixture
def tmp_session(tmp_path):
    """Create a BrowserSession with tmp_path directories."""
    return BrowserSession(
        headless=True,
        slow_mo=0,
        timeout=5000,
        screenshot_dir=tmp_path / "screenshots",
        state_path=tmp_path / "state.json",
    )


# =========================================================================
# Test: Initialization
# =========================================================================

class TestBrowserSessionInit:
    """Test BrowserSession construction and defaults."""

    def test_default_values(self, tmp_path):
        s = BrowserSession(screenshot_dir=tmp_path / "s")
        assert s._headless is False
        assert s._slow_mo == 100
        assert s._timeout == 30000
        assert s.is_started is False

    def test_creates_screenshot_dir(self, tmp_path):
        screen_dir = tmp_path / "new_dir"
        BrowserSession(screenshot_dir=screen_dir)
        assert screen_dir.exists()

    def test_not_started_initially(self, tmp_session):
        assert tmp_session.is_started is False

    def test_current_url_when_not_started(self, tmp_session):
        assert tmp_session.current_url == ""

    def test_current_title_returns_none(self, tmp_session):
        assert tmp_session.current_title is None


# =========================================================================
# Test: Lifecycle (mocked Playwright)
# =========================================================================

class TestBrowserSessionLifecycle:
    """Test start/close lifecycle with mocked Playwright."""

    @pytest.mark.asyncio
    async def test_start_launches_browser(self, tmp_session):
        pw, browser, context, page = _mock_playwright()
        with patch("src.browser.session.async_playwright") as mock_apw:
            mock_apw.return_value.start = AsyncMock(return_value=pw)
            await tmp_session.start()
            assert tmp_session.is_started is True
            pw.chromium.launch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_twice_warns(self, tmp_session):
        pw, browser, context, page = _mock_playwright()
        with patch("src.browser.session.async_playwright") as mock_apw:
            mock_apw.return_value.start = AsyncMock(return_value=pw)
            await tmp_session.start()
            # Second start should be a no-op (warns)
            await tmp_session.start()
            # Only one launch call
            pw.chromium.launch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_cleans_up(self, tmp_session):
        pw, browser, context, page = _mock_playwright()
        with patch("src.browser.session.async_playwright") as mock_apw:
            mock_apw.return_value.start = AsyncMock(return_value=pw)
            await tmp_session.start()
            await tmp_session.close()
            assert tmp_session.is_started is False
            context.close.assert_awaited_once()
            browser.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_when_not_started_is_noop(self, tmp_session):
        """close() on not-started session should not error."""
        await tmp_session.close()  # should not raise

    @pytest.mark.asyncio
    async def test_start_restores_saved_state(self, tmp_session):
        """If state file exists, it should be passed to new_context."""
        # Create a fake state file
        tmp_session._state_path.write_text('{"cookies": []}')

        pw, browser, context, page = _mock_playwright()
        with patch("src.browser.session.async_playwright") as mock_apw:
            mock_apw.return_value.start = AsyncMock(return_value=pw)
            await tmp_session.start()
            # Should have passed storage_state to new_context
            call_kwargs = browser.new_context.call_args
            assert call_kwargs.kwargs.get("storage_state") is not None


# =========================================================================
# Test: Guards (ensure_started)
# =========================================================================

class TestBrowserSessionGuards:
    """Test that operations fail gracefully when session not started."""

    def test_page_raises_when_not_started(self, tmp_session):
        with pytest.raises(BrowserSessionError, match="not started"):
            _ = tmp_session.page

    def test_context_raises_when_not_started(self, tmp_session):
        with pytest.raises(BrowserSessionError, match="not started"):
            _ = tmp_session.context

    @pytest.mark.asyncio
    async def test_goto_raises_when_not_started(self, tmp_session):
        with pytest.raises(BrowserSessionError, match="not started"):
            await tmp_session.goto("https://example.com")

    @pytest.mark.asyncio
    async def test_screenshot_raises_when_not_started(self, tmp_session):
        with pytest.raises(BrowserSessionError, match="not started"):
            await tmp_session.screenshot()

    @pytest.mark.asyncio
    async def test_save_state_raises_when_not_started(self, tmp_session):
        with pytest.raises(BrowserSessionError, match="not started"):
            await tmp_session.save_state()


# =========================================================================
# Test: Page operations (mocked)
# =========================================================================

class TestBrowserSessionOperations:
    """Test page operations with mocked Playwright."""

    async def _start_session(self, session):
        pw, browser, context, page = _mock_playwright()
        patcher = patch("src.browser.session.async_playwright")
        mock_apw = patcher.start()
        mock_apw.return_value.start = AsyncMock(return_value=pw)
        await session.start()
        return pw, browser, context, page, patcher

    @pytest.mark.asyncio
    async def test_goto_navigates(self, tmp_session):
        pw, browser, context, page, patcher = await self._start_session(tmp_session)
        try:
            await tmp_session.goto("https://example.com")
            page.goto.assert_awaited_once()
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_goto_failure_raises(self, tmp_session):
        pw, browser, context, page, patcher = await self._start_session(tmp_session)
        page.goto.side_effect = Exception("Network error")
        try:
            with pytest.raises(BrowserSessionError, match="Failed to navigate"):
                await tmp_session.goto("https://example.com")
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_screenshot_returns_bytes(self, tmp_session):
        pw, browser, context, page, patcher = await self._start_session(tmp_session)
        try:
            result = await tmp_session.screenshot()
            assert result == b"\x89PNG_test_bytes"
            assert tmp_session._screenshot_count == 1
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_screenshot_base64(self, tmp_session):
        pw, browser, context, page, patcher = await self._start_session(tmp_session)
        try:
            result = await tmp_session.screenshot_base64()
            assert isinstance(result, str)
            # Should be valid base64
            decoded = base64.b64decode(result)
            assert decoded == b"\x89PNG_test_bytes"
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_get_title(self, tmp_session):
        pw, browser, context, page, patcher = await self._start_session(tmp_session)
        try:
            title = await tmp_session.get_title()
            assert title == "Test Page"
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_get_text_content(self, tmp_session):
        pw, browser, context, page, patcher = await self._start_session(tmp_session)
        try:
            text = await tmp_session.get_text_content()
            assert text == "Hello World"
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_get_accessibility_tree(self, tmp_session):
        pw, browser, context, page, patcher = await self._start_session(tmp_session)
        try:
            tree = await tmp_session.get_accessibility_tree()
            assert tree["role"] == "document"
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_wait_for_load(self, tmp_session):
        pw, browser, context, page, patcher = await self._start_session(tmp_session)
        try:
            await tmp_session.wait_for_load("networkidle")
            page.wait_for_load_state.assert_awaited_once_with("networkidle")
        finally:
            patcher.stop()


# =========================================================================
# Test: State persistence
# =========================================================================

class TestBrowserSessionState:
    """Test state save/restore/clear."""

    def test_has_saved_state_false_initially(self, tmp_session):
        assert tmp_session.has_saved_state() is False

    def test_has_saved_state_true_after_file_created(self, tmp_session):
        tmp_session._state_path.write_text("{}")
        assert tmp_session.has_saved_state() is True

    def test_clear_saved_state(self, tmp_session):
        tmp_session._state_path.write_text("{}")
        tmp_session.clear_saved_state()
        assert not tmp_session._state_path.exists()

    def test_clear_saved_state_no_file_noop(self, tmp_session):
        tmp_session.clear_saved_state()  # should not raise


# =========================================================================
# Test: Compound engineering
# =========================================================================

class TestBrowserSessionCompound:
    """Test operation logging and lessons."""

    def test_operation_log_starts_empty(self, tmp_session):
        assert tmp_session.get_operation_log() == []

    def test_lessons_returns_failures(self, tmp_session):
        tmp_session._log_op("goto", success=False, error="timeout")
        tmp_session._log_op("screenshot", success=True)
        lessons = tmp_session.get_lessons()
        assert len(lessons) == 1
        assert lessons[0]["operation"] == "goto"

    def test_log_truncates_at_200(self, tmp_session):
        for i in range(250):
            tmp_session._log_op(f"op-{i}", success=True)
        assert len(tmp_session.get_operation_log()) == 200

    def test_from_settings_factory(self, tmp_path):
        settings = MagicMock()
        settings.browser_headless = True
        settings.browser_slow_mo = 50
        settings.browser_timeout = 10000
        settings.screenshot_dir = tmp_path / "screens"
        session = BrowserSession.from_settings(settings)
        assert session._headless is True
        assert session._slow_mo == 50


# =========================================================================
# Test: Async context manager
# =========================================================================

class TestBrowserSessionContextManager:
    """Test async with support."""

    @pytest.mark.asyncio
    async def test_context_manager(self, tmp_session):
        pw, browser, context, page = _mock_playwright()
        with patch("src.browser.session.async_playwright") as mock_apw:
            mock_apw.return_value.start = AsyncMock(return_value=pw)
            async with tmp_session as session:
                assert session.is_started is True
            assert tmp_session.is_started is False
