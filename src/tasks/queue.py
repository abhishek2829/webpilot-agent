"""WebPilot Agent — Async Task Queue (Task 14).

Manages background execution of workflows using a task queue pattern.
Two implementations:
  - InMemoryTaskQueue: zero-dependency fallback for development
  - (Future) CeleryTaskQueue: Redis-backed for production

Analogy: A restaurant kitchen ticket system.
  - WorkflowTask is an order ticket (what to cook and how)
  - TaskQueue is the ticket rail (submit, check status, cancel)
  - TaskResult is the plated dish (what came out)
  - InMemoryTaskQueue is a single-cook kitchen (handles one at a time)
  - CeleryTaskQueue is a full kitchen brigade (parallel execution)

Patterns applied:
- Strategy pattern: swap InMemory → Celery via TaskQueue protocol
- compound-engineering: get_stats() on queue for operational visibility
- Repository pattern: clean async interface for task state management
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol


# =========================================================================
# Task Status
# =========================================================================

class TaskStatus(Enum):
    """Lifecycle states for a queued workflow task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        """Whether this status represents a final state."""
        return self in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)


# =========================================================================
# Data Classes
# =========================================================================

@dataclass
class WorkflowTask:
    """A workflow execution request submitted to the queue.

    Attributes:
        task_id: Unique task identifier (auto-generated)
        workflow_name: Name of the workflow to execute
        variables: User-provided variables for the workflow
        checkpoint_mode: How to handle checkpoints (auto for background)
        headless: Whether to run browser in headless mode
    """
    workflow_name: str
    variables: dict[str, str] = field(default_factory=dict)
    checkpoint_mode: str = "auto"
    headless: bool = True
    task_id: str = field(default_factory=lambda: f"task-{uuid.uuid4().hex[:12]}")
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TaskResult:
    """The result/status of a queued task.

    Attributes:
        task_id: The task identifier
        workflow_name: Name of the workflow
        status: Current task status
        extracted_variables: Variables extracted during execution
        duration_ms: Total execution time in milliseconds
        error: Error message if failed
        created_at: When the task was created
        started_at: When execution began
        completed_at: When execution finished
    """
    task_id: str
    workflow_name: str
    status: TaskStatus
    extracted_variables: dict[str, str] = field(default_factory=dict)
    duration_ms: int = 0
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for API responses."""
        d: dict[str, Any] = {
            "task_id": self.task_id,
            "workflow_name": self.workflow_name,
            "status": self.status.value,
            "extracted_variables": self.extracted_variables,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at.isoformat(),
        }
        if self.error:
            d["error"] = self.error
        if self.started_at:
            d["started_at"] = self.started_at.isoformat()
        if self.completed_at:
            d["completed_at"] = self.completed_at.isoformat()
        return d


# =========================================================================
# TaskQueue Protocol
# =========================================================================

class TaskQueue(Protocol):
    """Protocol for task queue implementations.

    Both InMemoryTaskQueue and CeleryTaskQueue implement this interface.
    """

    async def submit(self, task: WorkflowTask) -> str: ...
    async def get_status(self, task_id: str) -> TaskResult | None: ...
    async def cancel(self, task_id: str) -> bool: ...
    async def update_status(self, task_id: str, status: TaskStatus) -> None: ...
    async def complete(
        self, task_id: str,
        extracted_variables: dict[str, str] | None = None,
        duration_ms: int = 0,
    ) -> None: ...
    async def fail(self, task_id: str, error: str) -> None: ...
    async def list_tasks(self, status: TaskStatus | None = None) -> list[TaskResult]: ...
    async def get_stats(self) -> dict[str, int]: ...


# =========================================================================
# InMemoryTaskQueue — Development Fallback
# =========================================================================

class InMemoryTaskQueue:
    """In-memory task queue for development and testing.

    No external dependencies (no Redis, no Celery). Tasks are stored
    in a dict and executed synchronously when processed.

    Limitations:
      - No persistence (tasks lost on restart)
      - No parallel execution
      - No real worker process
      - Not suitable for production

    Usage:
        queue = InMemoryTaskQueue()
        task_id = await queue.submit(WorkflowTask(workflow_name="clerk-setup"))
        result = await queue.get_status(task_id)
    """

    def __init__(self) -> None:
        self._tasks: dict[str, WorkflowTask] = {}
        self._results: dict[str, TaskResult] = {}
        self._stats = {
            "total_submitted": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }

    async def submit(self, task: WorkflowTask) -> str:
        """Submit a task to the queue.

        Returns the task ID for status tracking.
        """
        self._tasks[task.task_id] = task
        self._results[task.task_id] = TaskResult(
            task_id=task.task_id,
            workflow_name=task.workflow_name,
            status=TaskStatus.PENDING,
            created_at=task.created_at,
        )
        self._stats["total_submitted"] += 1
        return task.task_id

    async def get_status(self, task_id: str) -> TaskResult | None:
        """Get the current status of a task."""
        return self._results.get(task_id)

    async def cancel(self, task_id: str) -> bool:
        """Cancel a pending task.

        Returns True if cancelled, False if the task is already running/completed.
        """
        result = self._results.get(task_id)
        if not result:
            return False
        if result.status != TaskStatus.PENDING:
            return False

        result.status = TaskStatus.CANCELLED
        result.completed_at = datetime.now(timezone.utc)
        self._stats["cancelled"] += 1
        return True

    async def update_status(self, task_id: str, status: TaskStatus) -> None:
        """Update the status of a task."""
        result = self._results.get(task_id)
        if result:
            result.status = status
            if status == TaskStatus.RUNNING:
                result.started_at = datetime.now(timezone.utc)

    async def complete(
        self,
        task_id: str,
        extracted_variables: dict[str, str] | None = None,
        duration_ms: int = 0,
    ) -> None:
        """Mark a task as completed with results."""
        result = self._results.get(task_id)
        if result:
            result.status = TaskStatus.COMPLETED
            result.extracted_variables = extracted_variables or {}
            result.duration_ms = duration_ms
            result.completed_at = datetime.now(timezone.utc)
            self._stats["completed"] += 1

    async def fail(self, task_id: str, error: str) -> None:
        """Mark a task as failed with an error message."""
        result = self._results.get(task_id)
        if result:
            result.status = TaskStatus.FAILED
            result.error = error
            result.completed_at = datetime.now(timezone.utc)
            self._stats["failed"] += 1

    async def list_tasks(
        self, status: TaskStatus | None = None,
    ) -> list[TaskResult]:
        """List all tasks, optionally filtered by status."""
        results = list(self._results.values())
        if status:
            results = [r for r in results if r.status == status]
        return results

    async def get_stats(self) -> dict[str, int]:
        """Return queue statistics for operational visibility."""
        # Calculate live counts
        pending = sum(
            1 for r in self._results.values()
            if r.status == TaskStatus.PENDING
        )
        running = sum(
            1 for r in self._results.values()
            if r.status == TaskStatus.RUNNING
        )
        return {
            **self._stats,
            "pending": pending,
            "running": running,
        }
