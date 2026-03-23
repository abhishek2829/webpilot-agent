"""WebPilot Agent — Browser Session Pool.

Manages a pool of browser sessions for concurrent agent execution.
Sessions are created on demand, reused when idle, and cleaned up
after a configurable idle timeout.

Usage:
    pool = BrowserSessionPool(max_sessions=5)
    await pool.initialize()

    session = await pool.acquire(headless=True)
    try:
        # ... use session ...
    finally:
        await pool.release(session)

    await pool.shutdown()

For the multi-agent system, the pool is shared across all agents
to limit browser resource usage (each Chromium instance uses ~200MB RAM).
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PooledSession:
    """A browser session managed by the pool.

    Attributes:
        session: The underlying BrowserSession
        session_id: Unique identifier
        in_use: Whether the session is currently acquired
        created_at: When the session was created
        last_used_at: When the session was last released
    """
    session: Any  # BrowserSession — Any to avoid import at module level
    session_id: str
    in_use: bool = False
    created_at: float = field(default_factory=time.monotonic)
    last_used_at: float = field(default_factory=time.monotonic)


class BrowserSessionPool:
    """Pool of reusable browser sessions.

    Controls resource usage by limiting the number of concurrent
    browser instances. Sessions are lazily created and recycled.

    Thread safety: Uses asyncio.Lock for safe concurrent access.
    """

    def __init__(
        self,
        max_sessions: int = 5,
        idle_timeout_seconds: int = 300,
        headless: bool = True,
        slow_mo: int = 50,
    ) -> None:
        self._max_sessions = max_sessions
        self._idle_timeout = idle_timeout_seconds
        self._headless = headless
        self._slow_mo = slow_mo

        self._sessions: dict[str, PooledSession] = {}
        self._lock = asyncio.Lock()
        self._initialized = False

        self._stats = {
            "total_created": 0,
            "total_acquired": 0,
            "total_released": 0,
            "total_destroyed": 0,
        }

    async def initialize(self) -> None:
        """Initialize the pool (no sessions created yet — lazy creation)."""
        self._initialized = True
        logger.info(
            "Session pool initialized",
            extra={"max_sessions": self._max_sessions},
        )

    async def acquire(
        self,
        headless: bool | None = None,
    ) -> Any:
        """Acquire a browser session from the pool.

        Returns an idle session if available, otherwise creates a new one
        (up to max_sessions). Blocks if all sessions are in use.

        Args:
            headless: Override default headless setting for this session

        Returns:
            A BrowserSession ready for use

        Raises:
            RuntimeError: If the pool is not initialized or at capacity
        """
        if not self._initialized:
            raise RuntimeError("Session pool not initialized. Call initialize() first.")

        async with self._lock:
            # Try to find an idle session
            for pooled in self._sessions.values():
                if not pooled.in_use:
                    pooled.in_use = True
                    pooled.last_used_at = time.monotonic()
                    self._stats["total_acquired"] += 1
                    logger.debug(
                        "Reusing idle session",
                        extra={"session_id": pooled.session_id},
                    )
                    return pooled.session

            # No idle session — create a new one if under limit
            if len(self._sessions) < self._max_sessions:
                session = await self._create_session(headless)
                self._stats["total_acquired"] += 1
                return session

        # At capacity — raise error (caller can retry or queue)
        raise RuntimeError(
            f"Session pool at capacity ({self._max_sessions}). "
            "All sessions are in use."
        )

    async def release(self, session: Any) -> None:
        """Release a session back to the pool.

        The session remains open and can be reused by the next acquire() call.

        Args:
            session: The BrowserSession to release
        """
        async with self._lock:
            for pooled in self._sessions.values():
                if pooled.session is session:
                    pooled.in_use = False
                    pooled.last_used_at = time.monotonic()
                    self._stats["total_released"] += 1
                    logger.debug(
                        "Session released",
                        extra={"session_id": pooled.session_id},
                    )
                    return

        logger.warning("Attempted to release unknown session")

    async def shutdown(self) -> None:
        """Close all sessions and shut down the pool."""
        async with self._lock:
            for pooled in list(self._sessions.values()):
                try:
                    await pooled.session.close()
                    self._stats["total_destroyed"] += 1
                except Exception as e:
                    logger.warning(f"Error closing session {pooled.session_id}: {e}")

            self._sessions.clear()
            self._initialized = False

        logger.info("Session pool shut down")

    async def cleanup_idle(self) -> int:
        """Close sessions that have been idle longer than the timeout.

        Returns the number of sessions cleaned up.
        """
        now = time.monotonic()
        cleaned = 0

        async with self._lock:
            to_remove = []
            for sid, pooled in self._sessions.items():
                if (
                    not pooled.in_use
                    and (now - pooled.last_used_at) > self._idle_timeout
                ):
                    to_remove.append(sid)

            for sid in to_remove:
                pooled = self._sessions.pop(sid)
                try:
                    await pooled.session.close()
                    self._stats["total_destroyed"] += 1
                    cleaned += 1
                except Exception as e:
                    logger.warning(f"Error closing idle session {sid}: {e}")

        if cleaned:
            logger.info(f"Cleaned up {cleaned} idle sessions")

        return cleaned

    # =========================================================================
    # Internal
    # =========================================================================

    async def _create_session(self, headless: bool | None = None) -> Any:
        """Create a new browser session and add it to the pool."""
        from src.browser.session import BrowserSession

        session_id = f"session-{self._stats['total_created']:04d}"
        session = BrowserSession(
            headless=headless if headless is not None else self._headless,
            slow_mo=self._slow_mo,
        )
        await session.start()

        pooled = PooledSession(
            session=session,
            session_id=session_id,
            in_use=True,
        )
        self._sessions[session_id] = pooled
        self._stats["total_created"] += 1

        logger.info(
            "Created new browser session",
            extra={
                "session_id": session_id,
                "pool_size": len(self._sessions),
            },
        )

        return session

    # =========================================================================
    # Stats
    # =========================================================================

    @property
    def size(self) -> int:
        """Current number of sessions in the pool."""
        return len(self._sessions)

    @property
    def available(self) -> int:
        """Number of idle (available) sessions."""
        return sum(1 for p in self._sessions.values() if not p.in_use)

    @property
    def in_use(self) -> int:
        """Number of sessions currently in use."""
        return sum(1 for p in self._sessions.values() if p.in_use)

    def get_stats(self) -> dict[str, int]:
        """Return pool statistics."""
        return {
            **self._stats,
            "pool_size": self.size,
            "available": self.available,
            "in_use": self.in_use,
        }
