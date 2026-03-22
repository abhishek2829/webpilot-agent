"""WebPilot Agent — Structured Logging (Task 15).

Replaces stdlib logging with structlog for structured, context-rich,
filterable log output. Think of it as upgrading from plain text notes
to a searchable database — every log event carries structured metadata
that can be queried, aggregated, and analyzed.

Two output modes:
  - JSON: machine-readable, ideal for production log aggregation (ELK, Datadog)
  - Console: human-readable, colorized output for development

Key features:
  - Automatic context binding (execution_id, workflow_name propagate through calls)
  - Sensitive data filtering (API keys, passwords, tokens never appear in logs)
  - ExecutionLogger: per-execution structured logging with stats/lessons

Patterns applied:
- observability-engineer: structured logging as the foundation of observability
- compound-engineering: ExecutionLogger tracks events for get_stats()/get_lessons()
- security hardening: SensitiveDataFilter masks secrets in all log output
"""

from __future__ import annotations

import logging
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import structlog


# =========================================================================
# Sensitive Data Filter
# =========================================================================

# Keys that should always be masked (case-insensitive match)
_SENSITIVE_PATTERNS = re.compile(
    r"(api_key|apikey|password|passwd|secret|token|encryption_key|"
    r"auth_token|access_token|refresh_token|private_key|credential)",
    re.IGNORECASE,
)

_REDACTED = "***REDACTED***"


class SensitiveDataFilter:
    """Structlog processor that masks sensitive values in log event dicts.

    Any key matching common secret patterns (api_key, password, token, etc.)
    has its value replaced with '***REDACTED***'. Works recursively on
    nested dicts.

    Usage (as a structlog processor):
        structlog.configure(processors=[..., SensitiveDataFilter(), ...])
    """

    def __call__(
        self,
        logger: Any,
        method_name: str | None,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Filter sensitive data from the event dict."""
        return self._mask_dict(event_dict)

    def _mask_dict(self, d: dict[str, Any]) -> dict[str, Any]:
        """Recursively mask sensitive values in a dict."""
        result = {}
        for key, value in d.items():
            if isinstance(value, dict):
                result[key] = self._mask_dict(value)
            elif _SENSITIVE_PATTERNS.search(key):
                result[key] = _REDACTED
            else:
                result[key] = value
        return result


# =========================================================================
# Logging Setup
# =========================================================================

def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
) -> None:
    """Configure structlog and stdlib logging for the entire application.

    This should be called once at application startup (CLI main, API startup,
    or test fixtures).

    Args:
        log_level: Standard Python log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format — "json" for machine-readable, "console" for dev
    """
    # Normalize level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure stdlib logging (captures logs from third-party libs)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=numeric_level,
        force=True,
    )

    # Shared processors (run for every log event)
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        SensitiveDataFilter(),
    ]

    # Choose renderer based on format
    if log_format == "console":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        # Default to JSON (including for unknown formats)
        renderer = structlog.processors.JSONRenderer()

    # Configure structlog
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Set up a ProcessorFormatter for stdlib handlers
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # Replace handlers on root logger
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(numeric_level)


# =========================================================================
# Logger Factory
# =========================================================================

def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger bound to the given module name.

    Args:
        name: The module name (typically __name__)

    Returns:
        A bound structlog logger with context propagation
    """
    return structlog.get_logger(name)


# =========================================================================
# Context Binding (request/execution-scoped)
# =========================================================================

def bind_context(**kwargs: Any) -> None:
    """Bind key-value pairs to the current context (thread/coroutine-local).

    All subsequent log calls in this context will include these values.
    Use this at the start of a workflow execution to propagate execution_id,
    workflow_name, etc. through all nested function calls.

    Args:
        **kwargs: Key-value pairs to bind (e.g., execution_id="exec-123")
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all bound context variables.

    Call this after a workflow execution completes to avoid context leaking
    between executions.
    """
    structlog.contextvars.clear_contextvars()


# =========================================================================
# ExecutionLogger — Per-execution structured logging
# =========================================================================

class ExecutionLogger:
    """Structured logger for a single workflow execution.

    Provides typed log methods for each event type (step start, step complete,
    checkpoint, recovery, etc.) and tracks stats/lessons for compound-engineering.

    Analogy: A flight recorder (black box) for each workflow execution.
    Every event is recorded with full context, and after the flight (execution),
    you can pull stats and lessons from the recorder.

    Usage:
        el = ExecutionLogger(execution_id="exec-001", workflow_name="clerk-setup")
        el.log_step_start(0, "navigate", "Go to clerk.com")
        el.log_step_complete(0, "navigate", 1500)
        stats = el.get_stats()
        lessons = el.get_lessons()
    """

    def __init__(self, execution_id: str, workflow_name: str) -> None:
        self.execution_id = execution_id
        self.workflow_name = workflow_name
        self._logger = get_logger(f"execution.{execution_id}")
        self._events: list[dict[str, Any]] = []
        self._stats = {
            "step_starts": 0,
            "step_completions": 0,
            "step_failures": 0,
            "checkpoints": 0,
            "recovery_attempts": 0,
        }

    def log_step_start(
        self,
        step_index: int,
        step_type: str,
        description: str,
    ) -> None:
        """Log a step starting execution."""
        self._stats["step_starts"] += 1
        event = {
            "event_type": "step_start",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": self.execution_id,
            "workflow": self.workflow_name,
            "step_index": step_index,
            "step_type": step_type,
            "description": description,
        }
        self._events.append(event)
        self._logger.info(
            "step_start",
            step_index=step_index,
            step_type=step_type,
            description=description,
        )

    def log_step_complete(
        self,
        step_index: int,
        step_type: str,
        duration_ms: int,
    ) -> None:
        """Log a step completing successfully."""
        self._stats["step_completions"] += 1
        event = {
            "event_type": "step_complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": self.execution_id,
            "workflow": self.workflow_name,
            "step_index": step_index,
            "step_type": step_type,
            "duration_ms": duration_ms,
        }
        self._events.append(event)
        self._logger.info(
            "step_complete",
            step_index=step_index,
            step_type=step_type,
            duration_ms=duration_ms,
        )

    def log_step_failed(
        self,
        step_index: int,
        step_type: str,
        error: str,
        recovery_attempted: bool = False,
    ) -> None:
        """Log a step failure."""
        self._stats["step_failures"] += 1
        event = {
            "event_type": "step_failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": self.execution_id,
            "workflow": self.workflow_name,
            "step_index": step_index,
            "step_type": step_type,
            "error": error,
            "recovery_attempted": recovery_attempted,
        }
        self._events.append(event)
        self._logger.error(
            "step_failed",
            step_index=step_index,
            step_type=step_type,
            error=error,
            recovery_attempted=recovery_attempted,
        )

    def log_checkpoint(
        self,
        step_index: int,
        approved: bool,
        by: str,
        reason: str | None = None,
    ) -> None:
        """Log a checkpoint approval/rejection."""
        self._stats["checkpoints"] += 1
        event = {
            "event_type": "checkpoint",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": self.execution_id,
            "workflow": self.workflow_name,
            "step_index": step_index,
            "approved": approved,
            "by": by,
        }
        if reason:
            event["reason"] = reason
        self._events.append(event)
        self._logger.info(
            "checkpoint",
            step_index=step_index,
            approved=approved,
            by=by,
        )

    def log_recovery_attempt(
        self,
        step_index: int,
        strategy: str,
        resolved: bool,
        error: str | None = None,
    ) -> None:
        """Log a recovery attempt."""
        self._stats["recovery_attempts"] += 1
        event = {
            "event_type": "recovery_attempt",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": self.execution_id,
            "workflow": self.workflow_name,
            "step_index": step_index,
            "strategy": strategy,
            "resolved": resolved,
        }
        if error:
            event["error"] = error
        self._events.append(event)
        log_fn = self._logger.info if resolved else self._logger.warning
        log_fn(
            "recovery_attempt",
            step_index=step_index,
            strategy=strategy,
            resolved=resolved,
        )

    def log_execution_complete(
        self,
        status: str,
        total_steps: int,
        duration_ms: int,
        extracted_variables: list[str] | None = None,
    ) -> None:
        """Log the execution completion summary."""
        event = {
            "event_type": "execution_complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": self.execution_id,
            "workflow": self.workflow_name,
            "status": status,
            "total_steps": total_steps,
            "duration_ms": duration_ms,
            "extracted_variables": extracted_variables or [],
        }
        self._events.append(event)
        self._logger.info(
            "execution_complete",
            status=status,
            total_steps=total_steps,
            duration_ms=duration_ms,
            extracted_variables=extracted_variables or [],
        )

    # =========================================================================
    # Compound Engineering — Stats & Lessons
    # =========================================================================

    def get_stats(self) -> dict[str, int]:
        """Return event type counts for this execution."""
        return dict(self._stats)

    def get_lessons(self) -> list[dict[str, Any]]:
        """Return failure and recovery events as lessons.

        Following compound-engineering pattern: failures become lessons
        that improve future workflow definitions and execution strategies.
        """
        return [
            e for e in self._events
            if e.get("event_type") in ("step_failed", "recovery_attempt")
            and not e.get("resolved", False)
        ]
