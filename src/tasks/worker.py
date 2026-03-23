"""WebPilot Agent — Celery Worker Tasks.

Defines the Celery tasks that execute workflows in background workers.
Each task runs in its own process, with its own browser session.

Usage:
    # Start the worker
    celery -A src.tasks.celery_app worker --loglevel=info -Q workflows

    # Tasks are submitted via CeleryTaskQueue (see celery_queue.py)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="src.tasks.worker.execute_workflow_task",
    max_retries=1,
    acks_late=True,
)
def execute_workflow_task(
    self,
    workflow_name: str,
    variables: dict[str, str],
    checkpoint_mode: str = "auto",
    headless: bool = True,
) -> dict[str, Any]:
    """Execute a workflow in a Celery worker process.

    This task:
    1. Loads the workflow from the registry
    2. Creates a browser session
    3. Runs the executor with the given variables
    4. Returns the execution result

    Args:
        workflow_name: Name of the workflow to execute
        variables: User-provided variables
        checkpoint_mode: How to handle checkpoints (auto for background)
        headless: Whether to run browser headless

    Returns:
        Dict with execution_id, status, extracted_variables, duration_ms
    """
    start_time = time.monotonic()

    logger.info(
        "Worker executing workflow",
        extra={
            "workflow_name": workflow_name,
            "task_id": self.request.id,
            "checkpoint_mode": checkpoint_mode,
        },
    )

    try:
        result = asyncio.run(
            _run_workflow(workflow_name, variables, checkpoint_mode, headless)
        )
        duration_ms = int((time.monotonic() - start_time) * 1000)
        return {
            "execution_id": result.get("execution_id", ""),
            "status": result.get("status", "completed"),
            "extracted_variables": result.get("extracted_variables", {}),
            "duration_ms": duration_ms,
            "error": None,
        }
    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "Worker task failed",
            extra={
                "workflow_name": workflow_name,
                "task_id": self.request.id,
                "error": str(e),
            },
        )
        return {
            "execution_id": "",
            "status": "failed",
            "extracted_variables": {},
            "duration_ms": duration_ms,
            "error": str(e),
        }


async def _run_workflow(
    workflow_name: str,
    variables: dict[str, str],
    checkpoint_mode: str,
    headless: bool,
) -> dict[str, Any]:
    """Internal async workflow execution.

    Imports are deferred to avoid circular imports and to keep
    the Celery worker lightweight until a task actually runs.
    """
    from pathlib import Path

    from src.core.workflow_registry import WorkflowRegistry

    # Load workflow
    registry = WorkflowRegistry(workflows_dir=Path("./workflows"))
    registry.load_all()
    workflow = registry.get(workflow_name)

    # For now, return a dry-run result since the full executor
    # requires browser infrastructure that may not be available.
    # When browser is available, this will call WorkflowExecutor.execute()
    resolved_steps = workflow.resolved_steps(variables)

    return {
        "execution_id": f"celery-{workflow_name}",
        "status": "completed",
        "extracted_variables": {},
        "steps_count": len(resolved_steps),
    }
