"""Tests for WebPilot Agent — Configuration (Task 17 coverage).

Tests config loading from environment variables, validation, and defaults.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest


# =========================================================================
# Test: Settings loading and validation
# =========================================================================

class TestSettings:
    """Test Settings class loads from env vars correctly."""

    def test_settings_loads_from_env(self, tmp_path):
        """Should load all settings from environment variables."""
        env = {
            "ANTHROPIC_API_KEY": "sk-test-key-123",
            "VAULT_ENCRYPTION_KEY": "test-vault-key",
            "DATABASE_URL": "sqlite+aiosqlite:///test.db",
            "REDIS_URL": "redis://localhost:6379/1",
            "LOG_LEVEL": "DEBUG",
            "LOG_FORMAT": "json",
            "BROWSER_HEADLESS": "true",
            "BROWSER_SLOW_MO": "50",
            "BROWSER_TIMEOUT": "15000",
            "API_HOST": "127.0.0.1",
            "API_PORT": "9000",
            "API_SECRET_KEY": "test-secret",
            "CHECKPOINT_MODE": "auto",
            "CHECKPOINT_TIMEOUT": "120",
            "SCREENSHOT_DIR": str(tmp_path / "screenshots"),
            "WORKFLOWS_DIR": str(tmp_path / "workflows"),
        }
        with patch.dict(os.environ, env, clear=False):
            # Clear the lru_cache before testing
            from src.core.config import Settings
            s = Settings()
            assert s.anthropic_api_key == "sk-test-key-123"
            assert s.database_url == "sqlite+aiosqlite:///test.db"
            assert s.redis_url == "redis://localhost:6379/1"
            assert s.log_level == "DEBUG"
            assert s.browser_headless is True
            assert s.browser_slow_mo == 50
            assert s.api_host == "127.0.0.1"
            assert s.api_port == 9000
            assert s.checkpoint_mode == "auto"
            assert s.checkpoint_timeout == 120

    def test_default_values(self, tmp_path):
        """Should use sensible defaults when env vars aren't set."""
        env = {
            "ANTHROPIC_API_KEY": "sk-test",
            "VAULT_ENCRYPTION_KEY": "test-key",
            "SCREENSHOT_DIR": str(tmp_path / "screens"),
            "WORKFLOWS_DIR": str(tmp_path / "wf"),
        }
        with patch.dict(os.environ, env, clear=False):
            from src.core.config import Settings
            s = Settings()
            assert s.llm_model == "claude-sonnet-4-20250514"
            assert s.llm_max_tokens == 1024
            assert s.browser_headless is False
            assert s.browser_slow_mo == 100
            assert s.browser_timeout == 30000
            assert s.api_port == 8000
            assert s.checkpoint_mode == "cli"
            assert s.log_level == "INFO"

    def test_invalid_checkpoint_mode_rejected(self, tmp_path):
        """Should reject invalid checkpoint modes."""
        env = {
            "ANTHROPIC_API_KEY": "sk-test",
            "VAULT_ENCRYPTION_KEY": "test-key",
            "CHECKPOINT_MODE": "invalid",
            "SCREENSHOT_DIR": str(tmp_path / "screens"),
            "WORKFLOWS_DIR": str(tmp_path / "wf"),
        }
        from pydantic import ValidationError
        with patch.dict(os.environ, env, clear=False):
            from src.core.config import Settings
            with pytest.raises(ValidationError):
                Settings()

    def test_directory_validators_create_dirs(self, tmp_path):
        """Validators should create screenshot_dir and workflows_dir if they don't exist."""
        screens = tmp_path / "new_screenshots"
        workflows = tmp_path / "new_workflows"
        env = {
            "ANTHROPIC_API_KEY": "sk-test",
            "VAULT_ENCRYPTION_KEY": "test-key",
            "SCREENSHOT_DIR": str(screens),
            "WORKFLOWS_DIR": str(workflows),
        }
        with patch.dict(os.environ, env, clear=False):
            from src.core.config import Settings
            s = Settings()
            assert screens.exists()
            assert workflows.exists()

    def test_get_settings_returns_instance(self, tmp_path):
        """get_settings should return a Settings instance."""
        env = {
            "ANTHROPIC_API_KEY": "sk-test",
            "VAULT_ENCRYPTION_KEY": "test-key",
            "SCREENSHOT_DIR": str(tmp_path / "screens"),
            "WORKFLOWS_DIR": str(tmp_path / "wf"),
        }
        with patch.dict(os.environ, env, clear=False):
            from src.core.config import get_settings
            # Clear the cache
            get_settings.cache_clear()
            s = get_settings()
            assert s.anthropic_api_key == "sk-test"
            get_settings.cache_clear()
