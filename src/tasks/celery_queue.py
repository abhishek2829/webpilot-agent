"""WebPilot Agent — Celery-backed Task Queue.

Production implementation of the TaskQueue protocol using Celery + Redis.
Swaps in for InMemoryTaskQueue when Redis is available.

Usage:
    from src.tasks.celery_queue import CeleryTaskQueue
    from src.tasks.queue import WorkflowTask

    queue = CeleryTaskQueue()
    task_id = await queue.submit(WorkflowTask(workflow_name="clerk-setup"))
    result = await queue.get_status(task_id)

Patterns applied:
- Strategy pattern: implements same TaskQueue protocol as InMemoryTaskQueue
- compound-engineering: get_stats() for operational visibility
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.tasks.queue import TaskResult, TaskStatus, WorkflowTask

if TYPE_CHECKING:
    from celery import Celery
    from celery.result import AsyncResult as CeleryAsyncResult

logger = logging.getLogger(__name__)


def _get_celery_app():
    """Lazy import to avoid requiring celery at import time."""
    from src.tasks.celery_app import celery_app
    return celery_app


def _get_execute_task():
    """Lazy import to avoid requiring celery at import time."""
    from src.tasks.worker import execute_workflow_task
    return execute_workflow_task


class CeleryTaskQueue:
    """Celery-backed task queue for production workflow execution.

    Uses Redis as the message broker and result backend.
    Each workflow task runs in a separate Celery worker process.
    """

    def __init__(self) -> None:
        self._submitted: dict[str, WorkflowTask] = {}
        self._stats = {
            "total_submitted": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }

    async def submit(self, task: WorkflowTask) -> str:
        """Submit a workflow task to the Celery queue.

        The task is sent to a Celery worker for async execution.
        Returns the task ID for status tracking.
        """
        execute_task = _get_execute_task()
        celery_result = execute_task.apply_async(
            kwargs={
                "workflow_name": task.workflow_name,
                "variables": task.variables,
                "checkpoint_mode": task.checkpoint_mode,
                "headless": task.headless,
            },
            task_id=task.task_id,
        )

        self._submitted[task.task_id] = task
        self._stats["total_submitted"] += 1

        logger.info(
            "Task submitted to Celery",
            extra={
                "task_id": task.task_id,
                "workflow_name": task.workflow_name,
                "celery_id": celery_result.id,
            },
        )

        return task.task_id

    async def get_status(self, task_id: str) -> TaskResult | None:
        """Get the current status of a Celery task."""
        app = _get_celery_app()
        result = app.AsyncResult(task_id)
        task = self._submitted.get(task_id)

        if not task and not result.id:
            return None

        # Map Celery states to TaskStatus
        status_map = {
            "PENDING": TaskStatus.PENDING,
            "STARTED": TaskStatus.RUNNING,
            "SUCCESS": TaskStatus.COMPLETED,
            "FAILURE": TaskStatus.FAILED,
            "REVOKED": TaskStatus.CANCELLED,
        }

        task_status = status_map.get(result.state, TaskStatus.PENDING)

        task_result = TaskResult(
            task_id=task_id,
            workflow_name=task.workflow_name if task else "unknown",
            status=task_status,
            created_at=task.created_at if task else datetime.now(timezone.utc),
        )

        # Populate result data if task completed
        if result.state == "SUCCESS" and isinstance(result.result, dict):
            task_result.extracted_variables = result.result.get("extracted_variables", {})
            task_result.duration_ms = result.result.get("duration_ms", 0)
            task_result.completed_at = datetime.now(timezone.utc)
        elif result.state == "FAILURE":
            task_result.error = str(result.result) if result.result else "Unknown error"
            task_result.completed_at = datetime.now(timezone.utc)

        return task_result

    async def cancel(self, task_id: str) -> bool:
        """Cancel a pending/running Celery task."""
        app = _get_celery_app()
        result = app.AsyncResult(task_id)
        if result.state in ("SUCCESS", "FAILURE", "REVOKED"):
            return False

        app.control.revoke(task_id, terminate=True)
        self._stats["cancelled"] += 1
        return True

    async def update_status(self, task_id: str, status: TaskStatus) -> None:
        """Update task status (no-op for Celery — status is managed by Celery)."""
        pass

    async def complete(
        self,
        task_id: str,
        extracted_variables: dict[str, str] | None = None,
        duration_ms: int = 0,
    ) -> None:
        """Mark task as completed (no-op for Celery — completion is automatic)."""
        self._stats["completed"] += 1

    async def fail(self, task_id: str, error: str) -> None:
        """Mark task as failed (no-op for Celery — failure is automatic)."""
        self._stats["failed"] += 1

    async def list_tasks(
        self, status: TaskStatus | None = None,
    ) -> list[TaskResult]:
        """List all submitted tasks with current status."""
        results = []
        for task_id in self._submitted:
            task_result = await self.get_status(task_id)
            if task_result:
                if status is None or task_result.status == status:
                    results.append(task_result)
        return results

    async def get_stats(self) -> dict[str, int]:
        """Return queue statistics for operational visibility."""
        pending = 0
        running = 0
        for task_id in self._submitted:
            result = await self.get_status(task_id)
            if result:
                if result.status == TaskStatus.PENDING:
                    pending += 1
                elif result.status == TaskStatus.RUNNING:
                    running += 1
        return {
            **self._stats,
            "pending": pending,
            "running": running,
        }

    def get_lessons(self) -> list[dict]:
        """Compound-engineering: return failed tasks as lessons."""
        lessons = []
        if self._stats["failed"] > 0:
            lessons.append({
                "type": "failure_rate",
                "message": f"{self._stats['failed']} of {self._stats['total_submitted']} tasks failed",
                "suggestion": "Check worker logs for common failure patterns",
            })
        return lessons
