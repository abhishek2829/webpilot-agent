"""Tests for WebPilot Agent — Database Layer.

Following TDD discipline: tests written FIRST, then verified against implementation.
Covers: execution history storage, querying, and persistence using SQLite.

The database layer is the agent's memory — it stores execution history
so you can review what happened, when, and what was extracted.
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path

from src.core.models import ExecutionStatus


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
async def db(tmp_path: Path):
    """Create a test database instance."""
    from src.core.database import Database

    db_path = tmp_path / "test.db"
    database = Database(url=f"sqlite+aiosqlite:///{db_path}")
    await database.initialize()
    yield database
    await database.close()


# =========================================================================
# Table Creation
# =========================================================================

class TestDatabaseInit:

    @pytest.mark.asyncio
    async def test_initialize_creates_tables(self, tmp_path):
        from src.core.database import Database

        db_path = tmp_path / "init_test.db"
        database = Database(url=f"sqlite+aiosqlite:///{db_path}")
        await database.initialize()
        # Should not raise
        await database.close()

    @pytest.mark.asyncio
    async def test_initialize_is_idempotent(self, tmp_path):
        from src.core.database import Database

        db_path = tmp_path / "idempotent_test.db"
        database = Database(url=f"sqlite+aiosqlite:///{db_path}")
        await database.initialize()
        await database.initialize()  # Second call should not fail
        await database.close()


# =========================================================================
# Execution History — Save
# =========================================================================

class TestSaveExecution:

    @pytest.mark.asyncio
    async def test_save_execution(self, db):
        record = await db.save_execution(
            execution_id="exec-001",
            workflow_name="clerk-setup",
            status=ExecutionStatus.COMPLETED,
            duration_ms=5000,
            extracted_variables={"API_KEY": "pk_live_123"},
        )
        assert record is not None
        assert record.execution_id == "exec-001"

    @pytest.mark.asyncio
    async def test_save_failed_execution(self, db):
        record = await db.save_execution(
            execution_id="exec-002",
            workflow_name="clerk-setup",
            status=ExecutionStatus.FAILED,
            duration_ms=1000,
            error="Element not found",
        )
        assert record.status == ExecutionStatus.FAILED.value
        assert record.error == "Element not found"

    @pytest.mark.asyncio
    async def test_save_aborted_execution(self, db):
        record = await db.save_execution(
            execution_id="exec-003",
            workflow_name="clerk-setup",
            status=ExecutionStatus.ABORTED,
            duration_ms=2000,
        )
        assert record.status == ExecutionStatus.ABORTED.value


# =========================================================================
# Execution History — Query
# =========================================================================

class TestQueryExecutions:

    @pytest.mark.asyncio
    async def test_get_execution_by_id(self, db):
        await db.save_execution(
            execution_id="exec-get-001",
            workflow_name="clerk-setup",
            status=ExecutionStatus.COMPLETED,
            duration_ms=3000,
        )
        record = await db.get_execution("exec-get-001")
        assert record is not None
        assert record.workflow_name == "clerk-setup"

    @pytest.mark.asyncio
    async def test_get_nonexistent_execution(self, db):
        record = await db.get_execution("nonexistent")
        assert record is None

    @pytest.mark.asyncio
    async def test_list_executions(self, db):
        await db.save_execution(
            execution_id="exec-list-001",
            workflow_name="clerk-setup",
            status=ExecutionStatus.COMPLETED,
            duration_ms=1000,
        )
        await db.save_execution(
            execution_id="exec-list-002",
            workflow_name="vercel-deploy",
            status=ExecutionStatus.FAILED,
            duration_ms=2000,
        )
        records = await db.list_executions()
        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_list_executions_by_workflow(self, db):
        await db.save_execution(
            execution_id="exec-filter-001",
            workflow_name="clerk-setup",
            status=ExecutionStatus.COMPLETED,
            duration_ms=1000,
        )
        await db.save_execution(
            execution_id="exec-filter-002",
            workflow_name="vercel-deploy",
            status=ExecutionStatus.COMPLETED,
            duration_ms=2000,
        )
        records = await db.list_executions(workflow_name="clerk-setup")
        assert len(records) == 1
        assert records[0].workflow_name == "clerk-setup"

    @pytest.mark.asyncio
    async def test_list_executions_ordered_by_created(self, db):
        """Most recent executions should come first."""
        await db.save_execution(
            execution_id="exec-order-001",
            workflow_name="first",
            status=ExecutionStatus.COMPLETED,
            duration_ms=1000,
        )
        await db.save_execution(
            execution_id="exec-order-002",
            workflow_name="second",
            status=ExecutionStatus.COMPLETED,
            duration_ms=1000,
        )
        records = await db.list_executions()
        # Most recent first
        assert records[0].execution_id == "exec-order-002"

    @pytest.mark.asyncio
    async def test_list_executions_with_limit(self, db):
        for i in range(5):
            await db.save_execution(
                execution_id=f"exec-limit-{i:03d}",
                workflow_name="test",
                status=ExecutionStatus.COMPLETED,
                duration_ms=1000,
            )
        records = await db.list_executions(limit=3)
        assert len(records) == 3


# =========================================================================
# Extracted Variables
# =========================================================================

class TestExtractedVariables:

    @pytest.mark.asyncio
    async def test_variables_stored_as_json(self, db):
        await db.save_execution(
            execution_id="exec-vars-001",
            workflow_name="clerk-setup",
            status=ExecutionStatus.COMPLETED,
            duration_ms=3000,
            extracted_variables={
                "CLERK_KEY": "pk_live_abc",
                "CLERK_SECRET": "sk_live_xyz",
            },
        )
        record = await db.get_execution("exec-vars-001")
        assert record.extracted_variables is not None
        import json
        vars_dict = json.loads(record.extracted_variables)
        assert vars_dict["CLERK_KEY"] == "pk_live_abc"
        assert vars_dict["CLERK_SECRET"] == "sk_live_xyz"

    @pytest.mark.asyncio
    async def test_empty_variables(self, db):
        await db.save_execution(
            execution_id="exec-novars-001",
            workflow_name="test",
            status=ExecutionStatus.COMPLETED,
            duration_ms=1000,
        )
        record = await db.get_execution("exec-novars-001")
        # Should be None or empty JSON
        assert record.extracted_variables is None or record.extracted_variables == "{}"
