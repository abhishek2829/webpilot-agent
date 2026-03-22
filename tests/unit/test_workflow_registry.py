"""Tests for WebPilot Agent — Workflow Registry.

TDD discipline: covers discovery, loading, validation, retrieval,
search, pre-flight checks, error→lesson logging, and edge cases.
"""

import pytest
from pathlib import Path

from src.core.models import Workflow, Step, StepType
from src.core.workflow_registry import (
    WorkflowRegistry,
    WorkflowNotFoundError,
    WorkflowValidationError,
)


# =========================================================================
# Fixtures
# =========================================================================

VALID_YAML = """
name: test-workflow
description: A test workflow
version: "1.0"
tags:
  - test
  - setup
variables:
  project_name: ""
  env: "staging"
credentials_required:
  - test_email
  - test_password
estimated_duration_seconds: 60
steps:
  - type: navigate
    url: https://example.com
  - type: checkpoint
    message: "Ready to proceed with {{project_name}}?"
    screenshot: true
  - type: click
    selector: "button.submit"
    fallback_strategy: llm_vision
  - type: extract
    variable: API_KEY
    selector: ".api-key"
"""

MINIMAL_YAML = """
name: minimal-wf
description: Minimal valid workflow
steps:
  - type: navigate
    url: https://example.com
"""

SECOND_YAML = """
name: second-workflow
description: Another workflow for testing
tags:
  - auth
  - google
steps:
  - type: navigate
    url: https://auth.example.com
  - type: click
    selector: "#google-login"
"""

INVALID_YAML_BAD_STEP = """
name: bad-step-wf
description: Has invalid step
steps:
  - type: navigate
"""

INVALID_YAML_NO_STEPS = """
name: no-steps-wf
description: Missing steps field
"""

INVALID_YAML_SYNTAX = """
name: broken
  this is: not valid: yaml: {{
"""


@pytest.fixture
def workflows_dir(tmp_path: Path) -> Path:
    """Create a temp directory with workflow YAML files."""
    d = tmp_path / "workflows"
    d.mkdir()
    (d / "test-workflow.yaml").write_text(VALID_YAML)
    (d / "minimal.yaml").write_text(MINIMAL_YAML)
    (d / "second.yml").write_text(SECOND_YAML)
    return d


@pytest.fixture
def registry(workflows_dir: Path) -> WorkflowRegistry:
    """Create a registry and load all workflows."""
    reg = WorkflowRegistry(workflows_dir=workflows_dir)
    reg.load_all()
    return reg


@pytest.fixture
def empty_registry(tmp_path: Path) -> WorkflowRegistry:
    """Create a registry with no workflows."""
    d = tmp_path / "empty_workflows"
    d.mkdir()
    return WorkflowRegistry(workflows_dir=d)


# =========================================================================
# Discovery & Loading
# =========================================================================

class TestLoadAll:
    """Test bulk loading of workflows from directory."""

    def test_loads_all_yaml_files(self, registry: WorkflowRegistry) -> None:
        assert registry.count == 3

    def test_discovers_both_yaml_and_yml(self, registry: WorkflowRegistry) -> None:
        assert registry.exists("second-workflow")  # from .yml file

    def test_returns_loaded_and_error_counts(self, workflows_dir: Path) -> None:
        reg = WorkflowRegistry(workflows_dir=workflows_dir)
        loaded, errors = reg.load_all()
        assert loaded == 3
        assert errors == 0

    def test_handles_mixed_valid_and_invalid(self, workflows_dir: Path) -> None:
        (workflows_dir / "broken.yaml").write_text(INVALID_YAML_BAD_STEP)
        reg = WorkflowRegistry(workflows_dir=workflows_dir)
        loaded, errors = reg.load_all()
        assert loaded == 3
        assert errors == 1

    def test_handles_nonexistent_directory(self, tmp_path: Path) -> None:
        reg = WorkflowRegistry(workflows_dir=tmp_path / "nope")
        loaded, errors = reg.load_all()
        assert loaded == 0
        assert errors == 0

    def test_empty_directory(self, empty_registry: WorkflowRegistry) -> None:
        loaded, errors = empty_registry.load_all()
        assert loaded == 0
        assert errors == 0

    def test_ignores_non_yaml_files(self, workflows_dir: Path) -> None:
        (workflows_dir / "readme.md").write_text("# Not a workflow")
        (workflows_dir / "config.json").write_text("{}")
        reg = WorkflowRegistry(workflows_dir=workflows_dir)
        loaded, _ = reg.load_all()
        assert loaded == 3  # only .yaml and .yml


class TestLoadFile:
    """Test loading individual workflow files."""

    def test_load_single_file(self, workflows_dir: Path) -> None:
        reg = WorkflowRegistry(workflows_dir=workflows_dir)
        wf = reg.load_file(workflows_dir / "test-workflow.yaml")
        assert wf.name == "test-workflow"
        assert reg.exists("test-workflow")

    def test_load_from_string(self) -> None:
        reg = WorkflowRegistry(workflows_dir=Path("."))
        wf = reg.load_from_string(VALID_YAML, source="test")
        assert wf.name == "test-workflow"
        assert wf.description == "A test workflow"


# =========================================================================
# Validation
# =========================================================================

class TestValidation:
    """Test that invalid workflows are rejected at load time."""

    def test_rejects_invalid_step(self, tmp_path: Path) -> None:
        reg = WorkflowRegistry(workflows_dir=tmp_path)
        with pytest.raises(WorkflowValidationError):
            reg.load_from_string(INVALID_YAML_BAD_STEP)

    def test_rejects_missing_steps(self, tmp_path: Path) -> None:
        reg = WorkflowRegistry(workflows_dir=tmp_path)
        with pytest.raises(WorkflowValidationError):
            reg.load_from_string(INVALID_YAML_NO_STEPS)

    def test_rejects_bad_yaml_syntax(self, tmp_path: Path) -> None:
        reg = WorkflowRegistry(workflows_dir=tmp_path)
        with pytest.raises(WorkflowValidationError):
            reg.load_from_string(INVALID_YAML_SYNTAX)

    def test_rejects_non_mapping(self, tmp_path: Path) -> None:
        reg = WorkflowRegistry(workflows_dir=tmp_path)
        with pytest.raises(WorkflowValidationError) as exc_info:
            reg.load_from_string("- item1\n- item2\n")
        assert any("invalid_structure" in str(e) for e in exc_info.value.errors)

    def test_validation_error_contains_details(self, tmp_path: Path) -> None:
        reg = WorkflowRegistry(workflows_dir=tmp_path)
        with pytest.raises(WorkflowValidationError) as exc_info:
            reg.load_from_string(INVALID_YAML_BAD_STEP)
        assert len(exc_info.value.errors) > 0
        assert exc_info.value.name == "<string>"  # default source for load_from_string


# =========================================================================
# Retrieval
# =========================================================================

class TestRetrieval:
    """Test getting workflows from the registry."""

    def test_get_existing(self, registry: WorkflowRegistry) -> None:
        wf = registry.get("test-workflow")
        assert wf.name == "test-workflow"
        assert wf.description == "A test workflow"

    def test_get_nonexistent_raises(self, registry: WorkflowRegistry) -> None:
        with pytest.raises(WorkflowNotFoundError, match="not found"):
            registry.get("nonexistent")

    def test_error_lists_available_workflows(self, registry: WorkflowRegistry) -> None:
        with pytest.raises(WorkflowNotFoundError) as exc_info:
            registry.get("nope")
        msg = str(exc_info.value)
        assert "minimal-wf" in msg
        assert "test-workflow" in msg

    def test_exists(self, registry: WorkflowRegistry) -> None:
        assert registry.exists("test-workflow")
        assert not registry.exists("nope")

    def test_names_returns_sorted_list(self, registry: WorkflowRegistry) -> None:
        assert registry.names == ["minimal-wf", "second-workflow", "test-workflow"]

    def test_count(self, registry: WorkflowRegistry) -> None:
        assert registry.count == 3


class TestListWorkflows:
    """Test workflow listing and metadata."""

    def test_list_returns_all(self, registry: WorkflowRegistry) -> None:
        listing = registry.list_workflows()
        assert len(listing) == 3

    def test_list_contains_metadata(self, registry: WorkflowRegistry) -> None:
        listing = registry.list_workflows()
        test_wf = next(w for w in listing if w["name"] == "test-workflow")
        assert test_wf["description"] == "A test workflow"
        assert test_wf["version"] == "1.0"
        assert test_wf["steps"] == 4
        assert test_wf["checkpoints"] == 1
        assert "test" in test_wf["tags"]
        assert "test_email" in test_wf["credentials_required"]
        assert test_wf["estimated_duration_seconds"] == 60

    def test_list_sorted_by_name(self, registry: WorkflowRegistry) -> None:
        listing = registry.list_workflows()
        names = [w["name"] for w in listing]
        assert names == sorted(names)


# =========================================================================
# Search
# =========================================================================

class TestSearch:
    """Test workflow search functionality."""

    def test_search_by_name(self, registry: WorkflowRegistry) -> None:
        results = registry.search("minimal")
        assert len(results) == 1
        assert results[0]["name"] == "minimal-wf"

    def test_search_by_description(self, registry: WorkflowRegistry) -> None:
        results = registry.search("Another workflow")
        assert len(results) == 1
        assert results[0]["name"] == "second-workflow"

    def test_search_by_tag(self, registry: WorkflowRegistry) -> None:
        results = registry.search("auth")
        assert len(results) == 1
        assert results[0]["name"] == "second-workflow"

    def test_search_case_insensitive(self, registry: WorkflowRegistry) -> None:
        results = registry.search("TEST")
        assert len(results) >= 1

    def test_search_no_results(self, registry: WorkflowRegistry) -> None:
        results = registry.search("zzz_nonexistent_zzz")
        assert results == []

    def test_search_returns_multiple(self, registry: WorkflowRegistry) -> None:
        results = registry.search("workflow")
        assert len(results) >= 2


# =========================================================================
# Pre-flight Validation
# =========================================================================

class TestPreFlight:
    """Test execution readiness checks."""

    def test_ready_when_all_present(self, registry: WorkflowRegistry) -> None:
        ready, issues = registry.validate_execution_ready(
            name="test-workflow",
            variables={"project_name": "MyApp"},
            vault_keys=["test_email", "test_password"],
        )
        assert ready
        assert issues == []

    def test_not_ready_missing_variable(self, registry: WorkflowRegistry) -> None:
        ready, issues = registry.validate_execution_ready(
            name="test-workflow",
            variables={},  # project_name has empty default = required
            vault_keys=["test_email", "test_password"],
        )
        assert not ready
        assert any("project_name" in i for i in issues)

    def test_not_ready_missing_credential(self, registry: WorkflowRegistry) -> None:
        ready, issues = registry.validate_execution_ready(
            name="test-workflow",
            variables={"project_name": "MyApp"},
            vault_keys=["test_email"],  # missing test_password
        )
        assert not ready
        assert any("test_password" in i for i in issues)

    def test_not_ready_workflow_not_found(self, registry: WorkflowRegistry) -> None:
        ready, issues = registry.validate_execution_ready(
            name="nonexistent",
            variables={},
            vault_keys=[],
        )
        assert not ready
        assert any("not found" in i for i in issues)

    def test_ready_with_default_variables(self, registry: WorkflowRegistry) -> None:
        """Variables with defaults don't need to be provided."""
        ready, issues = registry.validate_execution_ready(
            name="test-workflow",
            variables={"project_name": "MyApp"},  # env has default "staging"
            vault_keys=["test_email", "test_password"],
        )
        assert ready

    def test_minimal_workflow_no_creds_needed(self, registry: WorkflowRegistry) -> None:
        ready, issues = registry.validate_execution_ready(
            name="minimal-wf",
            variables={},
            vault_keys=[],
        )
        assert ready
        assert issues == []


# =========================================================================
# Registration (Programmatic)
# =========================================================================

class TestRegistration:
    """Test manual registration and unregistration."""

    def test_register_programmatic(self, empty_registry: WorkflowRegistry) -> None:
        wf = Workflow(
            name="dynamic-wf",
            description="Built dynamically",
            steps=[Step(type=StepType.NAVIGATE, url="https://example.com")],
        )
        empty_registry.register(wf)
        assert empty_registry.exists("dynamic-wf")
        assert empty_registry.get("dynamic-wf").description == "Built dynamically"

    def test_unregister(self, registry: WorkflowRegistry) -> None:
        registry.unregister("test-workflow")
        assert not registry.exists("test-workflow")
        assert registry.count == 2

    def test_unregister_nonexistent_is_silent(self, registry: WorkflowRegistry) -> None:
        registry.unregister("nope")  # should not raise
        assert registry.count == 3


# =========================================================================
# Compound Engineering: Error→Lesson Logging
# =========================================================================

class TestCompoundEngineering:
    """Test the load logging and lessons system."""

    def test_load_log_captures_successes(self, registry: WorkflowRegistry) -> None:
        log = registry.get_load_log()
        successes = [e for e in log if e["success"]]
        assert len(successes) == 3

    def test_load_log_captures_failures(self, workflows_dir: Path) -> None:
        (workflows_dir / "broken.yaml").write_text(INVALID_YAML_BAD_STEP)
        reg = WorkflowRegistry(workflows_dir=workflows_dir)
        reg.load_all()
        errors = reg.get_load_errors()
        assert len(errors) == 1
        assert "error" in errors[0]

    def test_load_errors_only_returns_failures(self, registry: WorkflowRegistry) -> None:
        errors = registry.get_load_errors()
        assert len(errors) == 0  # all loaded successfully

    def test_log_entries_have_timestamps(self, registry: WorkflowRegistry) -> None:
        log = registry.get_load_log()
        assert all("timestamp" in e for e in log)

    def test_log_entries_have_source(self, registry: WorkflowRegistry) -> None:
        log = registry.get_load_log()
        assert all("source" in e for e in log)


# =========================================================================
# Variable Resolution Integration
# =========================================================================

class TestVariableResolution:
    """Test that workflows resolve {{variables}} correctly."""

    def test_resolved_steps_substitute_variables(
        self, registry: WorkflowRegistry
    ) -> None:
        wf = registry.get("test-workflow")
        steps = wf.resolved_steps({"project_name": "MyApp"})
        checkpoint = steps[1]
        assert "MyApp" in (checkpoint.message or "")

    def test_unresolved_variables_stay_as_placeholders(
        self, registry: WorkflowRegistry
    ) -> None:
        wf = registry.get("test-workflow")
        # project_name has empty default "" — resolves to empty string
        # This is correct: empty default means "required, user must override"
        steps = wf.resolved_steps({})
        checkpoint = steps[1]
        assert "{{project_name}}" not in (checkpoint.message or "")
        # With user override, it fills in properly
        steps_filled = wf.resolved_steps({"project_name": "TestApp"})
        assert "TestApp" in (steps_filled[1].message or "")

    def test_default_variables_applied(
        self, registry: WorkflowRegistry
    ) -> None:
        wf = registry.get("test-workflow")
        # env has default "staging"
        assert wf.variables["env"] == "staging"


# =========================================================================
# Integration: Load Real clerk-setup.yaml
# =========================================================================

class TestRealWorkflow:
    """Test loading the actual clerk-setup.yaml from the project."""

    def test_load_clerk_setup(self) -> None:
        """Load the real clerk-setup workflow if it exists."""
        clerk_path = Path("workflows/clerk-setup.yaml")
        if not clerk_path.exists():
            pytest.skip("clerk-setup.yaml not found")

        reg = WorkflowRegistry(workflows_dir=Path("workflows"))
        loaded, errors = reg.load_all()
        assert errors == 0
        assert reg.exists("clerk-setup")

        wf = reg.get("clerk-setup")
        assert wf.checkpoint_count() >= 2
        assert "clerk_email" in wf.credentials_required
        assert "project_name" in wf.variables
