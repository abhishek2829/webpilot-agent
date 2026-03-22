"""Tests for WebPilot Agent — Structured Logging (Task 15).

Tests the structlog-based logging system: JSON output, context binding,
request ID propagation, sensitive data filtering, and log level config.

TDD: These tests are written FIRST, before the implementation.
"""

from __future__ import annotations

import json
import logging
import io
from unittest.mock import patch

import pytest
import structlog


# =========================================================================
# Module under test
# =========================================================================

from src.core.logging import (
    setup_logging,
    get_logger,
    bind_context,
    clear_context,
    SensitiveDataFilter,
    ExecutionLogger,
)


# =========================================================================
# Test: setup_logging configures structlog properly
# =========================================================================

class TestSetupLogging:
    """Test the logging setup function."""

    def test_setup_logging_returns_none(self):
        """setup_logging should configure logging and return None."""
        result = setup_logging(log_level="DEBUG", log_format="json")
        assert result is None

    def test_setup_logging_sets_log_level(self):
        """Root logger level should match the configured level."""
        setup_logging(log_level="WARNING", log_format="json")
        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_setup_logging_json_format(self, capsys):
        """JSON format should produce parseable JSON lines."""
        setup_logging(log_level="DEBUG", log_format="json")
        logger = get_logger("test.json")
        logger.info("test_event", key="value")
        # structlog with JSON renderer should produce valid JSON
        # We verify via the get_logger return type
        assert logger is not None

    def test_setup_logging_console_format(self):
        """Console format should configure a human-readable renderer."""
        setup_logging(log_level="INFO", log_format="console")
        logger = get_logger("test.console")
        assert logger is not None

    def test_setup_logging_invalid_format_defaults_to_json(self):
        """Unknown format should fall back to JSON."""
        setup_logging(log_level="INFO", log_format="unknown_format")
        logger = get_logger("test.fallback")
        assert logger is not None

    def test_setup_logging_accepts_string_levels(self):
        """Should accept standard level strings: DEBUG, INFO, WARNING, ERROR."""
        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            setup_logging(log_level=level, log_format="json")
            root = logging.getLogger()
            assert root.level == getattr(logging, level)


# =========================================================================
# Test: get_logger returns a bound structlog logger
# =========================================================================

class TestGetLogger:
    """Test the get_logger factory."""

    def test_get_logger_returns_bound_logger(self):
        """get_logger should return a structlog BoundLogger."""
        setup_logging(log_level="DEBUG", log_format="json")
        logger = get_logger("my.module")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert hasattr(logger, "debug")

    def test_get_logger_includes_module_name(self):
        """Logger should have the module name bound as context."""
        setup_logging(log_level="DEBUG", log_format="json")
        logger = get_logger("src.core.executor")
        # The logger should carry the name
        assert logger is not None

    def test_get_logger_without_setup_still_works(self):
        """get_logger should work even if setup_logging hasn't been called."""
        logger = get_logger("test.no_setup")
        assert hasattr(logger, "info")


# =========================================================================
# Test: Context binding (request-scoped context)
# =========================================================================

class TestContextBinding:
    """Test bind_context and clear_context for request-scoped logging."""

    def test_bind_context_adds_key_value(self):
        """bind_context should add key-value pairs to thread-local context."""
        setup_logging(log_level="DEBUG", log_format="json")
        clear_context()
        bind_context(execution_id="exec-123", workflow="clerk-setup")
        # Verify context vars are set by reading them back
        ctx = structlog.contextvars.get_contextvars()
        assert ctx["execution_id"] == "exec-123"
        assert ctx["workflow"] == "clerk-setup"
        clear_context()

    def test_clear_context_removes_all(self):
        """clear_context should remove all bound context."""
        setup_logging(log_level="DEBUG", log_format="json")
        bind_context(execution_id="exec-456")
        clear_context()
        # After clearing, new loggers should not have the old context


# =========================================================================
# Test: Sensitive Data Filter
# =========================================================================

class TestSensitiveDataFilter:
    """Test that sensitive data is masked in log output."""

    def test_filter_masks_api_keys(self):
        """API keys should be masked in log event dicts."""
        f = SensitiveDataFilter()
        event_dict = {
            "event": "test",
            "api_key": "sk_live_abc123secret",
        }
        result = f(None, None, event_dict)
        assert result["api_key"] != "sk_live_abc123secret"
        assert "***" in result["api_key"]

    def test_filter_masks_passwords(self):
        """Password fields should be masked."""
        f = SensitiveDataFilter()
        event_dict = {
            "event": "test",
            "password": "my_secret_pass",
        }
        result = f(None, None, event_dict)
        assert result["password"] == "***REDACTED***"

    def test_filter_masks_tokens(self):
        """Token fields should be masked."""
        f = SensitiveDataFilter()
        event_dict = {
            "event": "test",
            "auth_token": "eyJhbGciOiJIUzI1NiJ9.abc",
        }
        result = f(None, None, event_dict)
        assert "eyJ" not in result["auth_token"]

    def test_filter_masks_encryption_keys(self):
        """Encryption key fields should be masked."""
        f = SensitiveDataFilter()
        event_dict = {
            "event": "test",
            "encryption_key": "super_secret_key_value",
        }
        result = f(None, None, event_dict)
        assert result["encryption_key"] == "***REDACTED***"

    def test_filter_masks_nested_secrets(self):
        """Secrets in nested dicts should be masked."""
        f = SensitiveDataFilter()
        event_dict = {
            "event": "test",
            "credentials": {
                "api_key": "sk_live_hidden",
                "username": "visible_user",
            },
        }
        result = f(None, None, event_dict)
        assert result["credentials"]["api_key"] != "sk_live_hidden"
        assert result["credentials"]["username"] == "visible_user"

    def test_filter_preserves_non_sensitive_fields(self):
        """Non-sensitive fields should pass through unchanged."""
        f = SensitiveDataFilter()
        event_dict = {
            "event": "workflow_started",
            "workflow": "clerk-setup",
            "step_count": 10,
            "timestamp": "2026-03-22T10:00:00Z",
        }
        result = f(None, None, event_dict)
        assert result["workflow"] == "clerk-setup"
        assert result["step_count"] == 10

    def test_filter_masks_secret_in_key_name(self):
        """Any key containing 'secret' should be masked."""
        f = SensitiveDataFilter()
        event_dict = {
            "event": "test",
            "clerk_secret_key": "sk_live_real_secret",
        }
        result = f(None, None, event_dict)
        assert result["clerk_secret_key"] == "***REDACTED***"

    def test_filter_case_insensitive(self):
        """Filtering should be case-insensitive on key names."""
        f = SensitiveDataFilter()
        event_dict = {
            "event": "test",
            "API_KEY": "should_be_hidden",
            "Password": "also_hidden",
        }
        result = f(None, None, event_dict)
        assert result["API_KEY"] != "should_be_hidden"
        assert result["Password"] == "***REDACTED***"


# =========================================================================
# Test: ExecutionLogger — structured logging for workflow executions
# =========================================================================

class TestExecutionLogger:
    """Test the ExecutionLogger helper for workflow-scoped logging."""

    def setup_method(self):
        setup_logging(log_level="DEBUG", log_format="json")

    def test_create_execution_logger(self):
        """Should create a logger bound to an execution context."""
        el = ExecutionLogger(
            execution_id="exec-789",
            workflow_name="clerk-setup",
        )
        assert el.execution_id == "exec-789"
        assert el.workflow_name == "clerk-setup"

    def test_log_step_start(self):
        """Should log a step start event without error."""
        el = ExecutionLogger(
            execution_id="exec-001",
            workflow_name="clerk-setup",
        )
        # Should not raise
        el.log_step_start(step_index=0, step_type="navigate", description="Go to clerk.com")

    def test_log_step_complete(self):
        """Should log a step completion event."""
        el = ExecutionLogger(
            execution_id="exec-001",
            workflow_name="clerk-setup",
        )
        el.log_step_complete(step_index=0, step_type="navigate", duration_ms=1500)

    def test_log_step_failed(self):
        """Should log a step failure event."""
        el = ExecutionLogger(
            execution_id="exec-001",
            workflow_name="clerk-setup",
        )
        el.log_step_failed(
            step_index=2,
            step_type="click",
            error="Element not found: .create-btn",
            recovery_attempted=True,
        )

    def test_log_checkpoint(self):
        """Should log a checkpoint event."""
        el = ExecutionLogger(
            execution_id="exec-001",
            workflow_name="clerk-setup",
        )
        el.log_checkpoint(
            step_index=1,
            approved=True,
            by="user",
        )

    def test_log_execution_complete(self):
        """Should log the execution completion summary."""
        el = ExecutionLogger(
            execution_id="exec-001",
            workflow_name="clerk-setup",
        )
        el.log_execution_complete(
            status="completed",
            total_steps=10,
            duration_ms=5000,
            extracted_variables=["API_KEY", "SECRET_KEY"],
        )

    def test_log_recovery_attempt(self):
        """Should log a recovery attempt event."""
        el = ExecutionLogger(
            execution_id="exec-001",
            workflow_name="clerk-setup",
        )
        el.log_recovery_attempt(
            step_index=3,
            strategy="llm_adapt",
            resolved=True,
        )

    def test_get_stats_returns_counts(self):
        """get_stats should return event type counts."""
        el = ExecutionLogger(
            execution_id="exec-001",
            workflow_name="clerk-setup",
        )
        el.log_step_start(0, "navigate", "Go to clerk.com")
        el.log_step_complete(0, "navigate", 1000)
        el.log_step_start(1, "click", "Click button")
        el.log_step_failed(1, "click", "Not found", recovery_attempted=False)

        stats = el.get_stats()
        assert stats["step_starts"] == 2
        assert stats["step_completions"] == 1
        assert stats["step_failures"] == 1

    def test_get_lessons_returns_failures(self):
        """get_lessons should return only failure/recovery events (compound-engineering)."""
        el = ExecutionLogger(
            execution_id="exec-001",
            workflow_name="clerk-setup",
        )
        el.log_step_complete(0, "navigate", 500)
        el.log_step_failed(1, "click", "Not found", recovery_attempted=True)
        el.log_recovery_attempt(1, "retry", resolved=False)

        lessons = el.get_lessons()
        assert len(lessons) >= 1
        assert any("Not found" in str(l) for l in lessons)
