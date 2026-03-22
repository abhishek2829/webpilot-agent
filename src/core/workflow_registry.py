"""WebPilot Agent — Workflow Registry.

Loads workflow YAML files from disk, validates them against domain models,
resolves {{variables}}, and serves them to the executor.

Think of this as the "recipe book shelf" — you pick a recipe by name,
the registry finds it, validates the ingredients list, and hands it
to the chef (executor) ready to cook.

Patterns applied:
- compound-engineering: Every load/validation logs outcome; failures become lessons
- autoresearch: Registry tracks which workflows succeed/fail at runtime,
  feeding data back for improvement
- GSD verification: Workflows are validated at load time, not execution time
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import ValidationError

from src.core.models import Workflow

logger = logging.getLogger(__name__)


class WorkflowNotFoundError(Exception):
    """Raised when a requested workflow doesn't exist in the registry."""
    pass


class WorkflowValidationError(Exception):
    """Raised when a YAML file fails schema validation."""

    def __init__(self, name: str, errors: list[dict]) -> None:
        self.name = name
        self.errors = errors
        super().__init__(
            f"Workflow '{name}' failed validation: {len(errors)} error(s)"
        )


class WorkflowRegistry:
    """Manages the lifecycle of workflow definitions.

    Responsibilities:
    1. Discover — scan a directory for .yaml/.yml workflow files
    2. Load — parse YAML into typed Workflow models
    3. Validate — reject malformed workflows at load time (GSD verify pattern)
    4. Serve — return workflows by name for execution
    5. Learn — track load successes/failures (compound-engineering pattern)

    Usage:
        registry = WorkflowRegistry(workflows_dir=Path("./workflows"))
        registry.load_all()

        workflow = registry.get("clerk-setup")
        steps = workflow.resolved_steps({"project_name": "MyApp"})
    """

    def __init__(self, workflows_dir: Path) -> None:
        self._dir = workflows_dir
        self._workflows: dict[str, Workflow] = {}
        self._load_errors: list[dict] = []
        self._load_log: list[dict] = []

    # =========================================================================
    # Discovery & Loading
    # =========================================================================

    def load_all(self) -> tuple[int, int]:
        """Discover and load all workflow YAML files from the directory.

        Returns:
            Tuple of (loaded_count, error_count)
        """
        if not self._dir.exists():
            logger.warning("Workflows directory does not exist: %s", self._dir)
            return 0, 0

        loaded = 0
        errors = 0
        yaml_files = sorted(
            list(self._dir.glob("*.yaml")) + list(self._dir.glob("*.yml"))
        )

        for path in yaml_files:
            try:
                workflow = self._load_file(path)
                self._workflows[workflow.name] = workflow
                self._log_load(path.name, workflow.name, success=True)
                loaded += 1
            except (WorkflowValidationError, yaml.YAMLError, Exception) as e:
                self._log_load(path.name, path.stem, success=False, error=str(e))
                errors += 1

        logger.info(
            "Registry loaded: %d workflows, %d errors from %s",
            loaded, errors, self._dir,
        )
        return loaded, errors

    def load_file(self, path: Path) -> Workflow:
        """Load a single workflow file and register it.

        Args:
            path: Path to the YAML file

        Returns:
            The loaded Workflow

        Raises:
            WorkflowValidationError: If the YAML is invalid
        """
        workflow = self._load_file(path)
        self._workflows[workflow.name] = workflow
        self._log_load(path.name, workflow.name, success=True)
        return workflow

    def load_from_string(self, yaml_content: str, source: str = "<string>") -> Workflow:
        """Load a workflow from a YAML string.

        Useful for dynamic workflow creation, API inputs, or testing.

        Args:
            yaml_content: Raw YAML string
            source: Label for logging

        Returns:
            The loaded Workflow
        """
        workflow = self._parse_and_validate(yaml_content, source)
        self._workflows[workflow.name] = workflow
        self._log_load(source, workflow.name, success=True)
        return workflow

    def _load_file(self, path: Path) -> Workflow:
        """Internal: read file and parse."""
        raw = path.read_text(encoding="utf-8")
        return self._parse_and_validate(raw, str(path.name))

    def _parse_and_validate(self, yaml_content: str, source: str) -> Workflow:
        """Parse YAML and validate against Workflow schema.

        GSD verification pattern: validate at load time, not execution time.
        Catch problems early, fail fast with clear messages.
        """
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise WorkflowValidationError(
                name=source,
                errors=[{"type": "yaml_parse_error", "msg": str(e)}],
            ) from e

        if not isinstance(data, dict):
            raise WorkflowValidationError(
                name=source,
                errors=[{"type": "invalid_structure", "msg": "YAML must be a mapping, not a sequence or scalar"}],
            )

        try:
            return Workflow(**data)
        except ValidationError as e:
            raise WorkflowValidationError(
                name=source,
                errors=[err for err in e.errors()],
            ) from e

    # =========================================================================
    # Retrieval
    # =========================================================================

    def get(self, name: str) -> Workflow:
        """Get a workflow by name.

        Args:
            name: Workflow identifier (e.g., "clerk-setup")

        Returns:
            The Workflow model

        Raises:
            WorkflowNotFoundError: If the workflow isn't registered
        """
        if name not in self._workflows:
            available = ", ".join(sorted(self._workflows.keys())) or "(none)"
            raise WorkflowNotFoundError(
                f"Workflow '{name}' not found. Available: {available}"
            )
        return self._workflows[name]

    def exists(self, name: str) -> bool:
        """Check if a workflow is registered."""
        return name in self._workflows

    def list_workflows(self) -> list[dict]:
        """List all registered workflows with metadata.

        Returns a summary suitable for CLI display or API response.
        """
        return [
            {
                "name": wf.name,
                "description": wf.description,
                "version": wf.version,
                "tags": wf.tags,
                "steps": len(wf.steps),
                "checkpoints": wf.checkpoint_count(),
                "credentials_required": wf.credentials_required,
                "estimated_duration_seconds": wf.estimated_duration_seconds,
            }
            for wf in sorted(self._workflows.values(), key=lambda w: w.name)
        ]

    def search(self, query: str) -> list[dict]:
        """Search workflows by name, description, or tags.

        Simple case-insensitive substring matching.
        """
        q = query.lower()
        results = []
        for wf in self._workflows.values():
            searchable = f"{wf.name} {wf.description} {' '.join(wf.tags)}".lower()
            if q in searchable:
                results.append({
                    "name": wf.name,
                    "description": wf.description,
                    "tags": wf.tags,
                })
        return results

    @property
    def count(self) -> int:
        """Number of registered workflows."""
        return len(self._workflows)

    @property
    def names(self) -> list[str]:
        """Sorted list of registered workflow names."""
        return sorted(self._workflows.keys())

    # =========================================================================
    # Registration (programmatic)
    # =========================================================================

    def register(self, workflow: Workflow) -> None:
        """Register a pre-built Workflow model directly.

        Useful for programmatically created workflows (e.g., from an API).
        """
        self._workflows[workflow.name] = workflow
        self._log_load("<programmatic>", workflow.name, success=True)

    def unregister(self, name: str) -> None:
        """Remove a workflow from the registry."""
        if name in self._workflows:
            del self._workflows[name]

    # =========================================================================
    # Compound Engineering: Load Logging (error→lesson pattern)
    # =========================================================================

    def _log_load(
        self, source: str, name: str, success: bool, error: str | None = None,
    ) -> None:
        """Track every load operation for the self-improvement loop."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "workflow_name": name,
            "success": success,
        }
        if error:
            entry["error"] = error
        self._load_log.append(entry)

    def get_load_log(self) -> list[dict]:
        """Full load history — for observability and debugging."""
        return list(self._load_log)

    def get_load_errors(self) -> list[dict]:
        """Only failed loads — compound-engineering lessons.

        Feed these into the self-learning agent to improve workflow
        YAML authoring, detect common mistakes, suggest fixes.
        """
        return [entry for entry in self._load_log if not entry["success"]]

    # =========================================================================
    # Validation Helpers
    # =========================================================================

    def validate_execution_ready(
        self, name: str, variables: dict[str, str], vault_keys: list[str],
    ) -> tuple[bool, list[str]]:
        """Check if a workflow is ready to execute.

        Pre-flight check before handing off to the executor:
        1. Workflow exists
        2. All required variables are provided
        3. All required credentials are in the vault

        Args:
            name: Workflow name
            variables: User-provided variables
            vault_keys: Keys currently in the credential vault

        Returns:
            Tuple of (ready, list_of_issues)
        """
        issues: list[str] = []

        if not self.exists(name):
            return False, [f"Workflow '{name}' not found"]

        wf = self.get(name)

        # Check variables
        for var_name, default_value in wf.variables.items():
            if not default_value and var_name not in variables:
                issues.append(f"Missing required variable: {var_name}")

        # Check credentials
        for cred_key in wf.credentials_required:
            if cred_key not in vault_keys:
                issues.append(f"Missing credential: {cred_key}")

        return len(issues) == 0, issues

    # =========================================================================
    # Factory
    # =========================================================================

    @classmethod
    def from_settings(cls, settings) -> WorkflowRegistry:
        """Create a registry from application settings."""
        registry = cls(workflows_dir=settings.workflows_dir)
        registry.load_all()
        return registry
