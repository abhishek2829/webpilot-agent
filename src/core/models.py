"""WebPilot Agent — Domain Models.

These models represent the core domain entities:
- Workflow: A reusable recipe (loaded from YAML)
- Step: A single browser action within a workflow
- WorkflowExecution: A runtime instance of a workflow
- CheckpointEvent: A pause point requiring human approval
- ExecutionResult: The outcome of running a workflow

Design principle: Domain model first, work backwards from the end goal.
The end goal is: "user says a sentence → agent does the web work → returns results"
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# Step Types — Every possible browser action
# =============================================================================

class StepType(str, Enum):
    """All possible step types in a workflow."""
    NAVIGATE = "navigate"       # Go to a URL
    CLICK = "click"             # Click an element
    TYPE = "type"               # Type text into an input
    EXTRACT = "extract"         # Copy a value from the page
    WAIT = "wait"               # Wait for a condition
    CHECKPOINT = "checkpoint"   # Pause for human approval
    SELECT = "select"           # Select from dropdown
    SCROLL = "scroll"           # Scroll to element/position
    SCREENSHOT = "screenshot"   # Take a screenshot (without checkpoint)


class FallbackStrategy(str, Enum):
    """What to do when the primary selector fails."""
    LLM_VISION = "llm_vision"   # Ask Claude to find the element via screenshot
    RETRY = "retry"             # Retry the same action after a brief wait
    SKIP = "skip"               # Skip this step (for optional actions)
    FAIL = "fail"               # Fail immediately


# =============================================================================
# Step — A single action in a workflow
# =============================================================================

class Step(BaseModel):
    """A single browser action within a workflow.
    
    Steps are the atomic unit of work. Each step represents one interaction
    with the browser: navigate, click, type, extract, wait, or checkpoint.
    
    The `fallback_strategy` field controls what happens when the primary
    selector fails — this is what makes the agent adaptive rather than brittle.
    """
    type: StepType
    description: str | None = Field(
        default=None,
        description="Human-readable description of what this step does (used by LLM fallback)"
    )

    # Navigation
    url: str | None = Field(default=None, description="URL to navigate to")

    # Element targeting
    selector: str | None = Field(
        default=None,
        description="CSS selector, XPath, or text selector (e.g., 'button:has-text(Create)')"
    )

    # Input
    text: str | None = Field(default=None, description="Text to type (supports {{variable}} syntax)")

    # Extraction
    variable: str | None = Field(
        default=None,
        description="Variable name to store extracted value (e.g., 'CLERK_API_KEY')"
    )
    extract_attribute: str = Field(
        default="textContent",
        description="Which attribute to extract (textContent, value, href, src, etc.)"
    )

    # Checkpoint
    message: str | None = Field(default=None, description="Message shown at checkpoint")
    screenshot: bool = Field(default=False, description="Take screenshot at this step")

    # Wait
    wait_for: str | None = Field(
        default=None,
        description="Selector or condition to wait for (e.g., 'networkidle', '.success-message')"
    )

    # Behavior
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    fallback_strategy: FallbackStrategy = Field(default=FallbackStrategy.LLM_VISION)
    optional: bool = Field(default=False, description="If true, failure is non-fatal")
    max_retries: int = Field(default=2, ge=0, le=5)

    @model_validator(mode="after")
    def validate_step_has_required_fields(self) -> Step:
        """Ensure step type has the fields it needs."""
        match self.type:
            case StepType.NAVIGATE:
                if not self.url:
                    raise ValueError("NAVIGATE step requires 'url'")
            case StepType.CLICK | StepType.SELECT:
                if not self.selector and not self.description:
                    raise ValueError(f"{self.type.value} step requires 'selector' or 'description'")
            case StepType.TYPE:
                if self.text is None:
                    raise ValueError("TYPE step requires 'text'")
            case StepType.EXTRACT:
                if not self.variable:
                    raise ValueError("EXTRACT step requires 'variable'")
            case StepType.CHECKPOINT:
                if not self.message:
                    raise ValueError("CHECKPOINT step requires 'message'")
        return self

    def resolve_variables(self, variables: dict[str, str]) -> Step:
        """Replace {{variable}} placeholders with actual values."""
        resolved = self.model_copy()
        pattern = re.compile(r"\{\{(\w+)\}\}")

        for field_name in ("url", "text", "selector", "message", "description"):
            value = getattr(resolved, field_name)
            if value and "{{" in value:
                resolved_value = pattern.sub(
                    lambda m: variables.get(m.group(1), m.group(0)),
                    value,
                )
                object.__setattr__(resolved, field_name, resolved_value)

        return resolved


# =============================================================================
# Workflow — A reusable recipe loaded from YAML
# =============================================================================

class Workflow(BaseModel):
    """A reusable workflow recipe — the 'recipe book' for the agent.
    
    Workflows are defined in YAML files and loaded at runtime. They describe
    a sequence of Steps the agent should execute, along with variables that
    can be customized per-execution and credentials the workflow needs.
    """
    name: str = Field(description="Unique workflow identifier (e.g., 'clerk-setup')")
    description: str = Field(description="What this workflow does")
    version: str = Field(default="1.0")
    tags: list[str] = Field(default_factory=list, description="For search/filter")

    steps: list[Step] = Field(min_length=1, description="Ordered list of browser actions")

    variables: dict[str, str] = Field(
        default_factory=dict,
        description="Variable defaults — user can override at execution time"
    )
    credentials_required: list[str] = Field(
        default_factory=list,
        description="Credential keys needed (e.g., ['clerk_email', 'clerk_password'])"
    )

    # Metadata
    estimated_duration_seconds: int = Field(default=120)
    author: str = Field(default="webpilot")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", v):
            raise ValueError(
                f"Workflow name must be lowercase alphanumeric with hyphens, got '{v}'"
            )
        return v

    def resolved_steps(self, user_variables: dict[str, str] | None = None) -> list[Step]:
        """Return steps with all {{variables}} replaced."""
        merged = {**self.variables, **(user_variables or {})}
        return [step.resolve_variables(merged) for step in self.steps]

    @classmethod
    def from_yaml(cls, yaml_content: str) -> Workflow:
        """Parse a YAML string into a Workflow model."""
        data = yaml.safe_load(yaml_content)
        if not isinstance(data, dict):
            raise ValueError("Workflow YAML must be a mapping")
        return cls(**data)

    @classmethod
    def from_yaml_file(cls, path: str) -> Workflow:
        """Load a workflow from a YAML file."""
        with open(path) as f:
            return cls.from_yaml(f.read())

    def checkpoint_count(self) -> int:
        """How many human checkpoints are in this workflow."""
        return sum(1 for s in self.steps if s.type == StepType.CHECKPOINT)


# =============================================================================
# Execution Models — Runtime state
# =============================================================================

class ExecutionStatus(str, Enum):
    """Possible states of a workflow execution."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"         # Waiting at a checkpoint
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"       # User rejected a checkpoint


class StepResult(BaseModel):
    """Result of executing a single step."""
    step_index: int
    step_type: StepType
    status: str = "success"
    data: dict[str, Any] = Field(default_factory=dict)
    screenshot_path: str | None = None
    duration_ms: int = 0
    error: str | None = None


class CheckpointEvent(BaseModel):
    """Emitted when the agent pauses at a checkpoint."""
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    execution_id: str
    step_index: int
    message: str
    screenshot_b64: str | None = None
    variables: dict[str, str] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CheckpointResult(BaseModel):
    """Human response to a checkpoint."""
    approved: bool
    by: str = "user"           # "user", "auto", "api_client"
    reason: str | None = None
    responded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutionResult(BaseModel):
    """Final result of running a workflow."""
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    workflow_name: str = ""
    status: ExecutionStatus
    step_results: list[StepResult] = Field(default_factory=list)
    extracted_variables: dict[str, str] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    error: str | None = None
    total_duration_ms: int = 0

    @property
    def success(self) -> bool:
        return self.status == ExecutionStatus.COMPLETED
