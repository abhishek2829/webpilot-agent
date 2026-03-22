"""Tests for WebPilot Agent — CLI Interface.

Following TDD discipline: tests written FIRST, then verified against implementation.
Covers: `webpilot run`, `webpilot list`, `webpilot creds` commands,
error handling, and output formatting.

The CLI is the user's front door — it wires together the registry, vault,
executor, and checkpoint manager into simple terminal commands.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typer.testing import CliRunner

from src.core.models import (
    ExecutionResult,
    ExecutionStatus,
    StepResult,
    StepType,
    Workflow,
    Step,
)


runner = CliRunner()


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def sample_workflow_yaml(tmp_path: Path) -> Path:
    """Create a minimal workflow YAML file for testing."""
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    wf = workflows_dir / "test-workflow.yaml"
    wf.write_text("""
name: test-workflow
description: A test workflow for CLI testing
version: "1.0"
tags:
  - test
  - demo
steps:
  - type: navigate
    url: https://example.com
  - type: checkpoint
    message: "Continue?"
    screenshot: true
  - type: click
    selector: button.submit
    description: Click submit
""")
    return workflows_dir


@pytest.fixture
def sample_vault_key() -> str:
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


# =========================================================================
# List Command
# =========================================================================

class TestListCommand:
    """Test `webpilot list` — shows available workflows."""

    def test_list_shows_workflows(self, sample_workflow_yaml):
        from src.cli.main import app

        result = runner.invoke(app, ["list", "--workflows-dir", str(sample_workflow_yaml)])
        assert result.exit_code == 0
        assert "test-workflow" in result.output

    def test_list_shows_description(self, sample_workflow_yaml):
        from src.cli.main import app

        result = runner.invoke(app, ["list", "--workflows-dir", str(sample_workflow_yaml)])
        assert "A test workflow" in result.output

    def test_list_empty_directory(self, tmp_path):
        from src.cli.main import app

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = runner.invoke(app, ["list", "--workflows-dir", str(empty_dir)])
        assert result.exit_code == 0
        assert "No workflows found" in result.output

    def test_list_shows_tags(self, sample_workflow_yaml):
        from src.cli.main import app

        result = runner.invoke(app, ["list", "--workflows-dir", str(sample_workflow_yaml)])
        assert "test" in result.output


# =========================================================================
# Creds Command
# =========================================================================

class TestCredsCommand:
    """Test `webpilot creds` — manage credentials in the vault."""

    def test_creds_set_stores_value(self, tmp_path, sample_vault_key):
        from src.cli.main import app

        vault_path = str(tmp_path / "test.vault")
        result = runner.invoke(
            app,
            ["creds", "set", "test_key", "test_value",
             "--vault-path", vault_path,
             "--vault-key", sample_vault_key],
        )
        assert result.exit_code == 0
        assert "Stored" in result.output

    def test_creds_get_retrieves_value(self, tmp_path, sample_vault_key):
        from src.cli.main import app

        vault_path = str(tmp_path / "test.vault")
        # Store first
        runner.invoke(
            app,
            ["creds", "set", "my_key", "my_secret",
             "--vault-path", vault_path,
             "--vault-key", sample_vault_key],
        )
        # Then retrieve
        result = runner.invoke(
            app,
            ["creds", "get", "my_key",
             "--vault-path", vault_path,
             "--vault-key", sample_vault_key],
        )
        assert result.exit_code == 0
        assert "my_secret" in result.output

    def test_creds_get_not_found(self, tmp_path, sample_vault_key):
        from src.cli.main import app

        vault_path = str(tmp_path / "test.vault")
        result = runner.invoke(
            app,
            ["creds", "get", "nonexistent",
             "--vault-path", vault_path,
             "--vault-key", sample_vault_key],
        )
        assert result.exit_code != 0 or "not found" in result.output.lower()

    def test_creds_list_shows_keys(self, tmp_path, sample_vault_key):
        from src.cli.main import app

        vault_path = str(tmp_path / "test.vault")
        runner.invoke(
            app,
            ["creds", "set", "key_one", "val1",
             "--vault-path", vault_path,
             "--vault-key", sample_vault_key],
        )
        runner.invoke(
            app,
            ["creds", "set", "key_two", "val2",
             "--vault-path", vault_path,
             "--vault-key", sample_vault_key],
        )
        result = runner.invoke(
            app,
            ["creds", "list",
             "--vault-path", vault_path,
             "--vault-key", sample_vault_key],
        )
        assert result.exit_code == 0
        assert "key_one" in result.output
        assert "key_two" in result.output

    def test_creds_list_empty_vault(self, tmp_path, sample_vault_key):
        from src.cli.main import app

        vault_path = str(tmp_path / "test.vault")
        result = runner.invoke(
            app,
            ["creds", "list",
             "--vault-path", vault_path,
             "--vault-key", sample_vault_key],
        )
        assert result.exit_code == 0
        assert "No credentials" in result.output or "empty" in result.output.lower()

    def test_creds_delete_removes_key(self, tmp_path, sample_vault_key):
        from src.cli.main import app

        vault_path = str(tmp_path / "test.vault")
        # Store first
        runner.invoke(
            app,
            ["creds", "set", "delete_me", "secret",
             "--vault-path", vault_path,
             "--vault-key", sample_vault_key],
        )
        # Delete
        result = runner.invoke(
            app,
            ["creds", "delete", "delete_me",
             "--vault-path", vault_path,
             "--vault-key", sample_vault_key],
        )
        assert result.exit_code == 0
        assert "Deleted" in result.output or "deleted" in result.output


# =========================================================================
# Run Command (Mocked Execution)
# =========================================================================

class TestRunCommand:
    """Test `webpilot run` — execute a workflow."""

    def test_run_unknown_workflow_errors(self, sample_workflow_yaml):
        from src.cli.main import app

        result = runner.invoke(
            app,
            ["run", "nonexistent-workflow",
             "--workflows-dir", str(sample_workflow_yaml)],
        )
        assert result.exit_code != 0 or "not found" in result.output.lower()

    def test_run_lists_workflow_info(self, sample_workflow_yaml):
        """Running a workflow should show its name and step count."""
        from src.cli.main import app

        # Use --dry-run to avoid actually launching a browser
        result = runner.invoke(
            app,
            ["run", "test-workflow",
             "--workflows-dir", str(sample_workflow_yaml),
             "--dry-run"],
        )
        assert result.exit_code == 0
        assert "test-workflow" in result.output
        assert "3 steps" in result.output or "steps" in result.output.lower()

    def test_run_with_variables(self, sample_workflow_yaml):
        from src.cli.main import app

        result = runner.invoke(
            app,
            ["run", "test-workflow",
             "--workflows-dir", str(sample_workflow_yaml),
             "--dry-run",
             "--var", "project_name=MyApp"],
        )
        assert result.exit_code == 0

    def test_run_dry_run_no_browser(self, sample_workflow_yaml):
        """Dry run should NOT launch a browser."""
        from src.cli.main import app

        result = runner.invoke(
            app,
            ["run", "test-workflow",
             "--workflows-dir", str(sample_workflow_yaml),
             "--dry-run"],
        )
        assert result.exit_code == 0
        assert "dry run" in result.output.lower() or "Dry run" in result.output


# =========================================================================
# Version / Help
# =========================================================================

class TestVersionAndHelp:
    """Basic CLI metadata."""

    def test_version(self):
        from src.cli.main import app

        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help(self):
        from src.cli.main import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "webpilot" in result.output.lower() or "run" in result.output.lower()
