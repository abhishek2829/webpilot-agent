"""Tests for WebPilot Agent — Async Task Queue (Task 14).

Tests the Celery + Redis task queue layer: task definitions,
execution tracking, result storage, and state management.

Since Redis and Celery aren't running in the test environment,
these tests use mocks and the in-memory fallback.

TDD: These tests are written FIRST, before the implementation.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tasks.queue import (
    TaskQueue,
    TaskStatus,
    TaskResult,
    InMemoryTaskQueue,
    WorkflowTask,
)


# =========================================================================
# Test: TaskStatus enum
# =========================================================================

class TestTaskStatus:
    """Test task status values."""

    def test_all_statuses_exist(self):
        """Should have all expected status values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"

    def test_status_is_terminal(self):
        """Terminal statuses should be identifiable."""
        assert TaskStatus.COMPLETED.is_terminal is True
        assert TaskStatus.FAILED.is_terminal is True
        assert TaskStatus.CANCELLED.is_terminal is True
        assert TaskStatus.PENDING.is_terminal is False
        assert TaskStatus.RUNNING.is_terminal is False


# =========================================================================
# Test: TaskResult dataclass
# =========================================================================

class TestTaskResult:
    """Test task result data structure."""

    def test_create_pending_result(self):
        """Should create a pending task result."""
        result = TaskResult(
            task_id="task-001",
            workflow_name="clerk-setup",
            status=TaskStatus.PENDING,
        )
        assert result.task_id == "task-001"
        assert result.workflow_name == "clerk-setup"
        assert result.status == TaskStatus.PENDING
        assert result.error is None
        assert result.extracted_variables == {}

    def test_create_completed_result(self):
        """Should create a completed task result with extracted variables."""
        result = TaskResult(
            task_id="task-002",
            workflow_name="clerk-setup",
            status=TaskStatus.COMPLETED,
            extracted_variables={"API_KEY": "pk_live_123"},
            duration_ms=5000,
        )
        assert result.status == TaskStatus.COMPLETED
        assert result.extracted_variables["API_KEY"] == "pk_live_123"
        assert result.duration_ms == 5000

    def test_create_failed_result(self):
        """Should create a failed task result with error."""
        result = TaskResult(
            task_id="task-003",
            workflow_name="clerk-setup",
            status=TaskStatus.FAILED,
            error="Element not found: .create-btn",
        )
        assert result.status == TaskStatus.FAILED
        assert "Element not found" in result.error

    def test_to_dict(self):
        """Should serialize to dictionary."""
        result = TaskResult(
            task_id="task-004",
            workflow_name="clerk-setup",
            status=TaskStatus.RUNNING,
        )
        d = result.to_dict()
        assert d["task_id"] == "task-004"
        assert d["status"] == "running"


# =========================================================================
# Test: WorkflowTask
# =========================================================================

class TestWorkflowTask:
    """Test workflow task definition."""

    def test_create_task(self):
        """Should create a workflow task."""
        task = WorkflowTask(
            workflow_name="clerk-setup",
            variables={"project_name": "MyApp"},
            checkpoint_mode="auto",
        )
        assert task.workflow_name == "clerk-setup"
        assert task.variables["project_name"] == "MyApp"
        assert task.checkpoint_mode == "auto"
        assert task.task_id is not None  # Auto-generated

    def test_task_has_unique_id(self):
        """Each task should get a unique ID."""
        task1 = WorkflowTask(workflow_name="clerk-setup")
        task2 = WorkflowTask(workflow_name="clerk-setup")
        assert task1.task_id != task2.task_id

    def test_task_default_headless(self):
        """Tasks should default to headless=True for background execution."""
        task = WorkflowTask(workflow_name="clerk-setup")
        assert task.headless is True


# =========================================================================
# Test: InMemoryTaskQueue (development fallback)
# =========================================================================

class TestInMemoryTaskQueue:
    """Test the in-memory task queue (no Redis required)."""

    @pytest.fixture
    def queue(self):
        return InMemoryTaskQueue()

    @pytest.mark.asyncio
    async def test_submit_returns_task_id(self, queue):
        """submit should return a task ID."""
        task = WorkflowTask(workflow_name="clerk-setup")
        task_id = await queue.submit(task)
        assert task_id == task.task_id

    @pytest.mark.asyncio
    async def test_get_status_pending(self, queue):
        """Newly submitted task should be pending."""
        task = WorkflowTask(workflow_name="clerk-setup")
        await queue.submit(task)
        result = await queue.get_status(task.task_id)
        assert result.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_status_unknown_task(self, queue):
        """Unknown task ID should return None."""
        result = await queue.get_status("nonexistent-task")
        assert result is None

    @pytest.mark.asyncio
    async def test_cancel_task(self, queue):
        """Should be able to cancel a pending task."""
        task = WorkflowTask(workflow_name="clerk-setup")
        await queue.submit(task)
        cancelled = await queue.cancel(task.task_id)
        assert cancelled is True
        result = await queue.get_status(task.task_id)
        assert result.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_running_task_fails(self, queue):
        """Cannot cancel a running task."""
        task = WorkflowTask(workflow_name="clerk-setup")
        await queue.submit(task)
        # Manually mark as running
        await queue.update_status(task.task_id, TaskStatus.RUNNING)
        cancelled = await queue.cancel(task.task_id)
        assert cancelled is False

    @pytest.mark.asyncio
    async def test_update_status(self, queue):
        """Should update task status."""
        task = WorkflowTask(workflow_name="clerk-setup")
        await queue.submit(task)
        await queue.update_status(task.task_id, TaskStatus.RUNNING)
        result = await queue.get_status(task.task_id)
        assert result.status == TaskStatus.RUNNING

    @pytest.mark.asyncio
    async def test_complete_task_with_result(self, queue):
        """Should store completion result with extracted variables."""
        task = WorkflowTask(workflow_name="clerk-setup")
        await queue.submit(task)
        await queue.update_status(task.task_id, TaskStatus.RUNNING)
        await queue.complete(
            task.task_id,
            extracted_variables={"API_KEY": "pk_123"},
            duration_ms=3000,
        )
        result = await queue.get_status(task.task_id)
        assert result.status == TaskStatus.COMPLETED
        assert result.extracted_variables["API_KEY"] == "pk_123"
        assert result.duration_ms == 3000

    @pytest.mark.asyncio
    async def test_fail_task_with_error(self, queue):
        """Should store failure with error message."""
        task = WorkflowTask(workflow_name="clerk-setup")
        await queue.submit(task)
        await queue.update_status(task.task_id, TaskStatus.RUNNING)
        await queue.fail(task.task_id, error="Timeout at step 3")
        result = await queue.get_status(task.task_id)
        assert result.status == TaskStatus.FAILED
        assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_list_tasks(self, queue):
        """Should list all tasks."""
        for i in range(3):
            await queue.submit(WorkflowTask(workflow_name=f"workflow-{i}"))
        tasks = await queue.list_tasks()
        assert len(tasks) == 3

    @pytest.mark.asyncio
    async def test_list_tasks_by_status(self, queue):
        """Should filter tasks by status."""
        t1 = WorkflowTask(workflow_name="wf-1")
        t2 = WorkflowTask(workflow_name="wf-2")
        await queue.submit(t1)
        await queue.submit(t2)
        await queue.update_status(t1.task_id, TaskStatus.RUNNING)
        running = await queue.list_tasks(status=TaskStatus.RUNNING)
        assert len(running) == 1
        assert running[0].task_id == t1.task_id

    @pytest.mark.asyncio
    async def test_get_stats(self, queue):
        """Should return queue statistics (compound-engineering)."""
        t1 = WorkflowTask(workflow_name="wf-1")
        t2 = WorkflowTask(workflow_name="wf-2")
        await queue.submit(t1)
        await queue.submit(t2)
        await queue.update_status(t1.task_id, TaskStatus.RUNNING)
        await queue.complete(t1.task_id, duration_ms=1000)

        stats = await queue.get_stats()
        assert stats["total_submitted"] == 2
        assert stats["completed"] == 1
        assert stats["pending"] == 1
