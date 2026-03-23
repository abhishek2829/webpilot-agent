"""Tests for WebPilot Agent — Workflow Library (Phase 4).

Validates that all pre-built workflow YAML files in the workflows/ directory:
1. Load without errors through the registry
2. Have correct metadata (name, tags, credentials, variables)
3. Pass variable resolution with required inputs
4. Have appropriate checkpoint placement
5. Pre-flight validation works for each workflow
"""

import pytest
from pathlib import Path

from src.core.models import Workflow, StepType
from src.core.workflow_registry import WorkflowRegistry


# =========================================================================
# Fixtures
# =========================================================================

WORKFLOWS_DIR = Path("workflows")

# Required variables for each workflow (the ones with empty defaults = required)
WORKFLOW_REQUIRED_VARS: dict[str, dict[str, str]] = {
    "clerk-setup": {"project_name": "TestApp"},
    "vercel-deploy": {"repo_url": "https://github.com/user/repo", "project_name": "test-project"},
    "supabase-setup": {"project_name": "TestProject", "database_password": "test-pass-123"},
    "stripe-setup": {"account_name": "TestBusiness"},
    "github-repo": {"repo_name": "test-repo", "github_username": "testuser"},
    "domain-setup": {"domain": "example.com", "vercel_project": "my-project"},
}

# Expected credentials for each workflow
WORKFLOW_CREDENTIALS: dict[str, list[str]] = {
    "clerk-setup": ["clerk_email", "clerk_password"],
    "vercel-deploy": ["vercel_email", "vercel_password"],
    "supabase-setup": ["supabase_email", "supabase_password"],
    "stripe-setup": ["stripe_email", "stripe_password"],
    "github-repo": ["github_email", "github_password"],
    "domain-setup": ["vercel_email", "vercel_password"],
}

# Expected tags for each workflow
WORKFLOW_TAGS: dict[str, list[str]] = {
    "clerk-setup": ["auth", "setup", "clerk"],
    "vercel-deploy": ["deploy", "hosting", "vercel"],
    "supabase-setup": ["database", "setup", "supabase"],
    "stripe-setup": ["payments", "setup", "stripe"],
    "github-repo": ["git", "setup", "github"],
    "domain-setup": ["domain", "dns", "setup"],
}


@pytest.fixture(scope="module")
def library_registry() -> WorkflowRegistry:
    """Load the full workflow library from disk."""
    if not WORKFLOWS_DIR.exists():
        pytest.skip("workflows/ directory not found")
    reg = WorkflowRegistry(workflows_dir=WORKFLOWS_DIR)
    reg.load_all()
    return reg


# =========================================================================
# Full Library Loading
# =========================================================================

class TestLibraryLoading:
    """Test that the entire workflow library loads without errors."""

    def test_all_workflows_load_without_errors(self) -> None:
        reg = WorkflowRegistry(workflows_dir=WORKFLOWS_DIR)
        loaded, errors = reg.load_all()
        assert errors == 0, f"Expected 0 load errors, got {errors}"
        assert loaded >= 6, f"Expected at least 6 workflows, got {loaded}"

    def test_all_expected_workflows_present(self, library_registry: WorkflowRegistry) -> None:
        expected = ["clerk-setup", "vercel-deploy", "supabase-setup", "stripe-setup", "github-repo", "domain-setup"]
        for name in expected:
            assert library_registry.exists(name), f"Workflow '{name}' not found in library"

    def test_no_duplicate_names(self, library_registry: WorkflowRegistry) -> None:
        listing = library_registry.list_workflows()
        names = [w["name"] for w in listing]
        assert len(names) == len(set(names)), f"Duplicate workflow names found: {names}"


# =========================================================================
# Individual Workflow Validation
# =========================================================================

class TestVercelDeploy:
    """Test vercel-deploy workflow structure."""

    def test_loads_correctly(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("vercel-deploy")
        assert wf.description == "Import a GitHub repo into Vercel and deploy it"
        assert wf.version == "1.0"

    def test_has_required_variables(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("vercel-deploy")
        assert "repo_url" in wf.variables
        assert "project_name" in wf.variables

    def test_has_checkpoints(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("vercel-deploy")
        assert wf.checkpoint_count() >= 2

    def test_has_deploy_tags(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("vercel-deploy")
        assert "deploy" in wf.tags
        assert "vercel" in wf.tags

    def test_extracts_deployment_url(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("vercel-deploy")
        extract_vars = [s.variable for s in wf.steps if s.type == StepType.EXTRACT and s.variable]
        assert "VERCEL_DEPLOYMENT_URL" in extract_vars


class TestSupabaseSetup:
    """Test supabase-setup workflow structure."""

    def test_loads_correctly(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("supabase-setup")
        assert "Supabase" in wf.description

    def test_has_required_variables(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("supabase-setup")
        assert "project_name" in wf.variables
        assert "database_password" in wf.variables

    def test_has_checkpoints(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("supabase-setup")
        assert wf.checkpoint_count() >= 3

    def test_extracts_api_keys(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("supabase-setup")
        extract_vars = [s.variable for s in wf.steps if s.type == StepType.EXTRACT and s.variable]
        assert "SUPABASE_URL" in extract_vars
        assert "SUPABASE_ANON_KEY" in extract_vars
        assert "SUPABASE_SERVICE_ROLE_KEY" in extract_vars

    def test_has_region_default(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("supabase-setup")
        assert wf.variables.get("region") == "us-east-1"


class TestStripeSetup:
    """Test stripe-setup workflow structure."""

    def test_loads_correctly(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("stripe-setup")
        assert "Stripe" in wf.description

    def test_has_required_variables(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("stripe-setup")
        assert "account_name" in wf.variables

    def test_has_checkpoints(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("stripe-setup")
        assert wf.checkpoint_count() >= 3

    def test_extracts_api_keys(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("stripe-setup")
        extract_vars = [s.variable for s in wf.steps if s.type == StepType.EXTRACT and s.variable]
        assert "STRIPE_PUBLISHABLE_KEY" in extract_vars
        assert "STRIPE_SECRET_KEY" in extract_vars

    def test_has_webhook_support(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("stripe-setup")
        assert "webhook_url" in wf.variables


class TestGithubRepo:
    """Test github-repo workflow structure."""

    def test_loads_correctly(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("github-repo")
        assert "GitHub" in wf.description

    def test_has_required_variables(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("github-repo")
        assert "repo_name" in wf.variables

    def test_has_checkpoints(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("github-repo")
        assert wf.checkpoint_count() >= 2

    def test_has_visibility_default(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("github-repo")
        assert wf.variables.get("visibility") == "private"

    def test_has_gitignore_template(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("github-repo")
        assert wf.variables.get("gitignore_template") == "Node"


class TestDomainSetup:
    """Test domain-setup workflow structure."""

    def test_loads_correctly(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("domain-setup")
        assert "domain" in wf.description.lower()

    def test_has_required_variables(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("domain-setup")
        assert "domain" in wf.variables
        assert "vercel_project" in wf.variables

    def test_has_checkpoints(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("domain-setup")
        assert wf.checkpoint_count() >= 3

    def test_extracts_dns_records(self, library_registry: WorkflowRegistry) -> None:
        wf = library_registry.get("domain-setup")
        extract_vars = [s.variable for s in wf.steps if s.type == StepType.EXTRACT and s.variable]
        assert "DNS_RECORD_TYPE" in extract_vars
        assert "DNS_RECORD_VALUE" in extract_vars


# =========================================================================
# Variable Resolution — All Workflows
# =========================================================================

class TestVariableResolution:
    """Test that all workflows resolve variables correctly."""

    @pytest.mark.parametrize("workflow_name", list(WORKFLOW_REQUIRED_VARS.keys()))
    def test_resolves_variables(self, library_registry: WorkflowRegistry, workflow_name: str) -> None:
        wf = library_registry.get(workflow_name)
        variables = WORKFLOW_REQUIRED_VARS[workflow_name]
        resolved = wf.resolved_steps(variables)
        # All steps should resolve without error
        assert len(resolved) > 0
        # Check no unresolved required variables remain in checkpoint messages
        for step in resolved:
            if step.type == StepType.CHECKPOINT and step.message:
                for var_name, var_value in variables.items():
                    if f"{{{{{var_name}}}}}" in (wf.variables.get(var_name, "") or ""):
                        continue
                    # The variable value should appear in the resolved message
                    assert var_value in step.message or f"{{{{{var_name}}}}}" not in step.message


# =========================================================================
# Pre-flight Checks — All Workflows
# =========================================================================

class TestPreFlightChecks:
    """Test pre-flight validation for all workflows."""

    @pytest.mark.parametrize("workflow_name", list(WORKFLOW_REQUIRED_VARS.keys()))
    def test_preflight_passes_with_all_inputs(self, library_registry: WorkflowRegistry, workflow_name: str) -> None:
        variables = WORKFLOW_REQUIRED_VARS[workflow_name]
        vault_keys = WORKFLOW_CREDENTIALS[workflow_name]
        ready, issues = library_registry.validate_execution_ready(
            name=workflow_name,
            variables=variables,
            vault_keys=vault_keys,
        )
        assert ready, f"{workflow_name} pre-flight failed: {issues}"

    @pytest.mark.parametrize("workflow_name", list(WORKFLOW_REQUIRED_VARS.keys()))
    def test_preflight_fails_missing_credentials(self, library_registry: WorkflowRegistry, workflow_name: str) -> None:
        variables = WORKFLOW_REQUIRED_VARS[workflow_name]
        ready, issues = library_registry.validate_execution_ready(
            name=workflow_name,
            variables=variables,
            vault_keys=[],  # no credentials
        )
        assert not ready
        assert len(issues) > 0

    @pytest.mark.parametrize("workflow_name", list(WORKFLOW_REQUIRED_VARS.keys()))
    def test_preflight_fails_missing_variables(self, library_registry: WorkflowRegistry, workflow_name: str) -> None:
        vault_keys = WORKFLOW_CREDENTIALS[workflow_name]
        ready, issues = library_registry.validate_execution_ready(
            name=workflow_name,
            variables={},  # no variables
            vault_keys=vault_keys,
        )
        # Should fail because required variables have empty defaults
        assert not ready


# =========================================================================
# Credentials — All Workflows
# =========================================================================

class TestCredentials:
    """Test that all workflows declare the expected credentials."""

    @pytest.mark.parametrize("workflow_name", list(WORKFLOW_CREDENTIALS.keys()))
    def test_has_expected_credentials(self, library_registry: WorkflowRegistry, workflow_name: str) -> None:
        wf = library_registry.get(workflow_name)
        expected = WORKFLOW_CREDENTIALS[workflow_name]
        for cred in expected:
            assert cred in wf.credentials_required, (
                f"{workflow_name} missing credential '{cred}'"
            )


# =========================================================================
# Tags — All Workflows
# =========================================================================

class TestTags:
    """Test that all workflows have the expected tags."""

    @pytest.mark.parametrize("workflow_name", list(WORKFLOW_TAGS.keys()))
    def test_has_expected_tags(self, library_registry: WorkflowRegistry, workflow_name: str) -> None:
        wf = library_registry.get(workflow_name)
        expected = WORKFLOW_TAGS[workflow_name]
        for tag in expected:
            assert tag in wf.tags, f"{workflow_name} missing tag '{tag}'"

    def test_search_finds_all_setup_workflows(self, library_registry: WorkflowRegistry) -> None:
        results = library_registry.search("setup")
        setup_names = {r["name"] for r in results}
        assert "clerk-setup" in setup_names
        assert "supabase-setup" in setup_names
        assert "stripe-setup" in setup_names
        assert "github-repo" in setup_names  # has 'setup' tag
        assert "domain-setup" in setup_names


# =========================================================================
# Workflow Structure Quality
# =========================================================================

class TestWorkflowQuality:
    """Test structural quality across all workflows."""

    @pytest.mark.parametrize("workflow_name", list(WORKFLOW_REQUIRED_VARS.keys()))
    def test_first_step_is_navigate(self, library_registry: WorkflowRegistry, workflow_name: str) -> None:
        """Every workflow should start by navigating to a URL."""
        wf = library_registry.get(workflow_name)
        assert wf.steps[0].type == StepType.NAVIGATE

    @pytest.mark.parametrize("workflow_name", list(WORKFLOW_REQUIRED_VARS.keys()))
    def test_last_step_is_screenshot(self, library_registry: WorkflowRegistry, workflow_name: str) -> None:
        """Every workflow should end with a screenshot for the execution log."""
        wf = library_registry.get(workflow_name)
        assert wf.steps[-1].type == StepType.SCREENSHOT

    @pytest.mark.parametrize("workflow_name", list(WORKFLOW_REQUIRED_VARS.keys()))
    def test_has_at_least_two_checkpoints(self, library_registry: WorkflowRegistry, workflow_name: str) -> None:
        """Safety: every workflow should pause at least twice for human approval."""
        wf = library_registry.get(workflow_name)
        assert wf.checkpoint_count() >= 2

    @pytest.mark.parametrize("workflow_name", list(WORKFLOW_REQUIRED_VARS.keys()))
    def test_all_checkpoints_have_screenshot(self, library_registry: WorkflowRegistry, workflow_name: str) -> None:
        """Checkpoints should include screenshots for human review."""
        wf = library_registry.get(workflow_name)
        for step in wf.steps:
            if step.type == StepType.CHECKPOINT:
                assert step.screenshot, (
                    f"{workflow_name}: checkpoint at step missing screenshot=true"
                )

    @pytest.mark.parametrize("workflow_name", list(WORKFLOW_REQUIRED_VARS.keys()))
    def test_has_estimated_duration(self, library_registry: WorkflowRegistry, workflow_name: str) -> None:
        wf = library_registry.get(workflow_name)
        assert wf.estimated_duration_seconds > 0

    @pytest.mark.parametrize("workflow_name", list(WORKFLOW_REQUIRED_VARS.keys()))
    def test_has_author(self, library_registry: WorkflowRegistry, workflow_name: str) -> None:
        wf = library_registry.get(workflow_name)
        assert wf.author == "webpilot"
