"""WebPilot Agent — Database Layer.

Stores execution history using SQLAlchemy async with SQLite (development)
or PostgreSQL (production). The swap is a one-line config change.

Analogy: The agent's diary. Every workflow execution gets an entry:
when it ran, whether it succeeded, how long it took, and what it extracted.
This lets you review history, debug failures, and track patterns.

Patterns applied:
- SQLAlchemy 2.0 async patterns (async_sessionmaker)
- Repository pattern for clean data access
- SQLite for zero-setup development, PostgreSQL-ready for production
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, Integer, String, Text, desc
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.core.models import ExecutionStatus

logger = logging.getLogger(__name__)


# =========================================================================
# ORM Models
# =========================================================================

class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""
    pass


class ExecutionRecord(Base):
    """Stores the result of a single workflow execution."""
    __tablename__ = "executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(String(50), unique=True, nullable=False, index=True)
    workflow_name = Column(String(100), nullable=False, index=True)
    status = Column(String(20), nullable=False)
    duration_ms = Column(Integer, default=0)
    extracted_variables = Column(Text, nullable=True)  # JSON string
    error = Column(Text, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


# =========================================================================
# Database Class
# =========================================================================

class Database:
    """Async database access layer for execution history.

    Usage:
        db = Database(url="sqlite+aiosqlite:///./data/webpilot.db")
        await db.initialize()

        await db.save_execution(
            execution_id="abc123",
            workflow_name="clerk-setup",
            status=ExecutionStatus.COMPLETED,
            duration_ms=5000,
            extracted_variables={"API_KEY": "pk_live_123"},
        )

        record = await db.get_execution("abc123")
        history = await db.list_executions(workflow_name="clerk-setup")

        await db.close()

    Swap SQLite to PostgreSQL by changing the URL:
        url="postgresql+asyncpg://user:pass@localhost:5432/webpilot"
    """

    def __init__(self, url: str = "sqlite+aiosqlite:///./data/webpilot.db") -> None:
        self._engine: AsyncEngine = create_async_engine(url, echo=False)
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )

    async def initialize(self) -> None:
        """Create all tables. Safe to call multiple times (idempotent)."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized", extra={"engine": str(self._engine.url)})

    async def close(self) -> None:
        """Dispose of the engine and connection pool."""
        await self._engine.dispose()

    # =========================================================================
    # Save
    # =========================================================================

    async def save_execution(
        self,
        execution_id: str,
        workflow_name: str,
        status: ExecutionStatus,
        duration_ms: int = 0,
        extracted_variables: dict[str, str] | None = None,
        error: str | None = None,
    ) -> ExecutionRecord:
        """Save a workflow execution record.

        Args:
            execution_id: Unique execution identifier
            workflow_name: Name of the workflow that was executed
            status: Final execution status (completed, failed, aborted)
            duration_ms: Total execution time in milliseconds
            extracted_variables: Variables extracted during execution
            error: Error message if execution failed

        Returns:
            The saved ExecutionRecord
        """
        record = ExecutionRecord(
            execution_id=execution_id,
            workflow_name=workflow_name,
            status=status.value,
            duration_ms=duration_ms,
            extracted_variables=(
                json.dumps(extracted_variables) if extracted_variables else None
            ),
            error=error,
            created_at=datetime.now(timezone.utc),
        )

        async with self._session_factory() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)

        logger.info(
            "Execution saved",
            extra={
                "execution_id": execution_id,
                "workflow": workflow_name,
                "status": status.value,
            },
        )

        return record

    # =========================================================================
    # Query
    # =========================================================================

    async def get_execution(self, execution_id: str) -> ExecutionRecord | None:
        """Get a single execution by ID.

        Returns None if not found.
        """
        from sqlalchemy import select

        async with self._session_factory() as session:
            stmt = select(ExecutionRecord).where(
                ExecutionRecord.execution_id == execution_id
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_executions(
        self,
        workflow_name: str | None = None,
        limit: int = 50,
    ) -> list[ExecutionRecord]:
        """List execution history, most recent first.

        Args:
            workflow_name: Filter by workflow name (optional)
            limit: Maximum number of records to return

        Returns:
            List of ExecutionRecord ordered by created_at descending
        """
        from sqlalchemy import select

        stmt = select(ExecutionRecord).order_by(
            desc(ExecutionRecord.created_at)
        ).limit(limit)

        if workflow_name:
            stmt = stmt.where(ExecutionRecord.workflow_name == workflow_name)

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())
