"""Tests for WebPilot Agent — CeleryTaskQueue (Phase 4).

Tests the CeleryTaskQueue implementation without requiring a running
Redis/Celery instance. Uses mocks to simulate Celery behavior.
"""

import asyncio

import pytest
from unittest.mock import MagicMock, patch

from src.tasks.queue import TaskStatus, WorkflowTask
from src.tasks.celery_queue import CeleryTaskQueue


# =========================================================================
# Helpers
# =========================================================================

def run(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def queue() -> CeleryTaskQueue:
    return CeleryTaskQueue()


@pytest.fixture
def sample_task() -> WorkflowTask:
    return WorkflowTask(
        workflow_name="clerk-setup",
        variables={"project_name": "TestApp"},
        checkpoint_mode="auto",
        headless=True,
    )


def mock_execute_task():
    """Create a mock for the execute_workflow_task Celery task."""
    mock = MagicMock()
    return mock


def mock_celery_app(state="PENDING", result=None):
    """Create a mock Celery app with configurable AsyncResult."""
    app = MagicMock()
    mock_result = MagicMock()
    mock_result.state = state
    mock_result.id = "mock-id" if state != "PENDING" else None
    mock_result.result = result
    app.AsyncResult.return_value = mock_result
    return app


# =========================================================================
# Submit
# =========================================================================

class TestSubmit:
    """Test task submission to Celery queue."""

    def test_submit_returns_task_id(self, queue: CeleryTaskQueue, sample_task: WorkflowTask) -> None:
        mock_task = mock_execute_task()
        mock_task.apply_async.return_value = MagicMock(id=sample_task.task_id)

        with patch("src.tasks.celery_queue._get_execute_task", return_value=mock_task):
            task_id = run(queue.submit(sample_task))
            assert task_id == sample_task.task_id

    def test_submit_calls_apply_async(self, queue: CeleryTaskQueue, sample_task: WorkflowTask) -> None:
        mock_task = mock_execute_task()
        mock_task.apply_async.return_value = MagicMock(id=sample_task.task_id)

        with patch("src.tasks.celery_queue._get_execute_task", return_value=mock_task):
            run(queue.submit(sample_task))

            mock_task.apply_async.assert_called_once_with(
                kwargs={
                    "workflow_name": "clerk-setup",
                    "variables": {"project_name": "TestApp"},
                    "checkpoint_mode": "auto",
                    "headless": True,
                },
                task_id=sample_task.task_id,
            )

    def test_submit_increments_stats(self, queue: CeleryTaskQueue, sample_task: WorkflowTask) -> None:
        mock_task = mock_execute_task()
        mock_task.apply_async.return_value = MagicMock(id=sample_task.task_id)

        with patch("src.tasks.celery_queue._get_execute_task", return_value=mock_task):
            run(queue.submit(sample_task))

        # Stats don't require celery
        assert queue._stats["total_submitted"] == 1


# =========================================================================
# Status
# =========================================================================

class TestGetStatus:
    """Test getting task status from Celery."""

    def _submit_task(self, queue, sample_task):
        """Helper to submit a task with mocked Celery."""
        mock_task = mock_execute_task()
        mock_task.apply_async.return_value = MagicMock(id=sample_task.task_id)
        with patch("src.tasks.celery_queue._get_execute_task", return_value=mock_task):
            run(queue.submit(sample_task))

    def test_get_status_pending(self, queue: CeleryTaskQueue, sample_task: WorkflowTask) -> None:
        self._submit_task(queue, sample_task)

        app = mock_celery_app(state="PENDING")
        app.AsyncResult.return_value.id = sample_task.task_id  # has id because we submitted it

        with patch("src.tasks.celery_queue._get_celery_app", return_value=app):
            result = run(queue.get_status(sample_task.task_id))
            assert result is not None
            assert result.status == TaskStatus.PENDING

    def test_get_status_completed(self, queue: CeleryTaskQueue, sample_task: WorkflowTask) -> None:
        self._submit_task(queue, sample_task)

        app = mock_celery_app(
            state="SUCCESS",
            result={"extracted_variables": {"API_KEY": "pk_test_123"}, "duration_ms": 5000},
        )

        with patch("src.tasks.celery_queue._get_celery_app", return_value=app):
            result = run(queue.get_status(sample_task.task_id))
            assert result is not None
            assert result.status == TaskStatus.COMPLETED
            assert result.extracted_variables == {"API_KEY": "pk_test_123"}
            assert result.duration_ms == 5000

    def test_get_status_failed(self, queue: CeleryTaskQueue, sample_task: WorkflowTask) -> None:
        self._submit_task(queue, sample_task)

        app = mock_celery_app(state="FAILURE", result=Exception("Browser crashed"))

        with patch("src.tasks.celery_queue._get_celery_app", return_value=app):
            result = run(queue.get_status(sample_task.task_id))
            assert result is not None
            assert result.status == TaskStatus.FAILED
            assert "Browser crashed" in (result.error or "")

    def test_get_status_unknown_task(self, queue: CeleryTaskQueue) -> None:
        app = mock_celery_app(state="PENDING")
        app.AsyncResult.return_value.id = None

        with patch("src.tasks.celery_queue._get_celery_app", return_value=app):
            result = run(queue.get_status("nonexistent-task"))
            assert result is None


# =========================================================================
# Cancel
# =========================================================================

class TestCancel:
    """Test task cancellation."""

    def test_cancel_pending_task(self, queue: CeleryTaskQueue) -> None:
        app = mock_celery_app(state="PENDING")

        with patch("src.tasks.celery_queue._get_celery_app", return_value=app):
            cancelled = run(queue.cancel("some-task-id"))
            assert cancelled
            app.control.revoke.assert_called_once_with("some-task-id", terminate=True)

    def test_cannot_cancel_completed_task(self, queue: CeleryTaskQueue) -> None:
        app = mock_celery_app(state="SUCCESS")

        with patch("src.tasks.celery_queue._get_celery_app", return_value=app):
            cancelled = run(queue.cancel("completed-task"))
            assert not cancelled


# =========================================================================
# Stats & Lessons
# =========================================================================

class TestStatsAndLessons:
    """Test operational visibility features."""

    def test_initial_stats_no_celery_needed(self, queue: CeleryTaskQueue) -> None:
        # get_stats calls get_status which needs celery, but with no submitted tasks it's fine
        assert queue._stats["total_submitted"] == 0
        assert queue._stats["completed"] == 0
        assert queue._stats["failed"] == 0

    def test_no_lessons_when_no_failures(self, queue: CeleryTaskQueue) -> None:
        lessons = queue.get_lessons()
        assert lessons == []

    def test_lessons_after_failure(self, queue: CeleryTaskQueue) -> None:
        run(queue.fail("some-task", "test error"))
        lessons = queue.get_lessons()
        assert len(lessons) == 1
        assert "failed" in lessons[0]["message"]

    def test_stats_track_completions(self, queue: CeleryTaskQueue) -> None:
        run(queue.complete("task-1", {"key": "value"}, 1000))
        assert queue._stats["completed"] == 1

    def test_stats_track_cancellations(self, queue: CeleryTaskQueue) -> None:
        app = mock_celery_app(state="PENDING")
        with patch("src.tasks.celery_queue._get_celery_app", return_value=app):
            run(queue.cancel("task-1"))
        assert queue._stats["cancelled"] == 1
