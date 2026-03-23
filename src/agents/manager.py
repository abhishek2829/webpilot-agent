"""WebPilot Agent — Manager Agent.

The orchestrator that chains multiple agents together to execute
complex multi-step business workflows. This is the "brain" that
decomposes high-level goals into agent tasks and coordinates execution.

Example pipeline:
    "Research 10 AI dev tool companies, find CTOs on LinkedIn,
     send connection requests, and log everything in HubSpot."

    Manager decomposes this into:
    1. ResearchAgent → competitor-analysis (10x)
    2. ResearchAgent → lead-research (for each company's CTO)
    3. SalesAgent → linkedin-connect (for each CTO)
    4. SalesAgent → crm-entry (log each interaction)

Architecture:
    ManagerAgent (THIS — the conductor)
    ├── DevOpsSetupAgent
    ├── ResearchAgent
    ├── SalesAgent
    ├── MarketingAgent
    └── FinanceAgent
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.agents.base import (
    AgentCapability,
    AgentRegistry,
    AgentResult,
    AgentStatus,
    AgentTask,
)
from src.agents.dispatcher import AgentDispatcher

logger = logging.getLogger(__name__)


# =========================================================================
# Pipeline Models
# =========================================================================

@dataclass
class PipelineStep:
    """A single step in a multi-agent pipeline.

    Attributes:
        agent_name: Which agent to use (or "auto" for dispatcher routing)
        action: The workflow/action to execute
        parameters: Static parameters for the action
        input_mapping: Map output from previous steps to this step's parameters.
                       Format: {"param_name": "step_N.variable_name"}
        condition: Optional condition to check before executing.
                   Format: "step_N.success == true"
    """
    action: str
    parameters: dict[str, str] = field(default_factory=dict)
    agent_name: str = "auto"
    input_mapping: dict[str, str] = field(default_factory=dict)
    condition: str = ""


@dataclass
class Pipeline:
    """A multi-agent pipeline — a sequence of steps across different agents.

    Attributes:
        name: Pipeline identifier
        description: What this pipeline accomplishes
        steps: Ordered list of pipeline steps
    """
    name: str
    description: str
    steps: list[PipelineStep]


@dataclass
class PipelineResult:
    """Result of executing a complete pipeline."""
    pipeline_name: str
    success: bool
    step_results: list[AgentResult]
    total_duration_ms: int = 0
    error: str | None = None
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_name": self.pipeline_name,
            "success": self.success,
            "steps_completed": len([r for r in self.step_results if r.success]),
            "steps_total": len(self.step_results),
            "total_duration_ms": self.total_duration_ms,
            "error": self.error,
            "step_results": [r.to_dict() for r in self.step_results],
            "completed_at": self.completed_at.isoformat(),
        }


# =========================================================================
# Pre-built Pipelines
# =========================================================================

BUILTIN_PIPELINES: dict[str, Pipeline] = {
    "full-saas-setup": Pipeline(
        name="full-saas-setup",
        description="Complete SaaS project setup: GitHub repo + Clerk auth + Supabase DB + Vercel deploy + Stripe payments",
        steps=[
            PipelineStep(action="github-repo", parameters={"visibility": "private"}, agent_name="devops-setup"),
            PipelineStep(action="clerk-setup", agent_name="devops-setup"),
            PipelineStep(action="supabase-setup", agent_name="devops-setup"),
            PipelineStep(action="stripe-setup", agent_name="devops-setup"),
            PipelineStep(action="vercel-deploy", agent_name="devops-setup"),
        ],
    ),
    "outbound-pipeline": Pipeline(
        name="outbound-pipeline",
        description="Research a company, find decision makers, send LinkedIn connection, log in CRM",
        steps=[
            PipelineStep(action="lead-research", agent_name="auto"),
            PipelineStep(action="linkedin-connect", agent_name="auto", input_mapping={"prospect_url": "step_0.KEY_PEOPLE"}),
            PipelineStep(action="crm-entry", agent_name="auto", input_mapping={"contact_name": "step_0.COMPANY_NAME"}),
        ],
    ),
    "content-launch": Pipeline(
        name="content-launch",
        description="Research a topic, create blog outline, set up newsletter, post on social media",
        steps=[
            PipelineStep(action="content-research", agent_name="auto"),
            PipelineStep(action="blog-outline", agent_name="auto", input_mapping={"blog_topic": "step_0.HEADING_STRUCTURE"}),
            PipelineStep(action="newsletter-setup", agent_name="auto"),
            PipelineStep(action="social-post", agent_name="auto"),
        ],
    ),
    "revenue-health-check": Pipeline(
        name="revenue-health-check",
        description="Check revenue metrics, audit subscriptions, monitor payments, extract expense report",
        steps=[
            PipelineStep(action="revenue-dashboard", agent_name="auto"),
            PipelineStep(action="invoice-tracker", agent_name="auto"),
            PipelineStep(action="payment-monitor", agent_name="auto"),
            PipelineStep(action="subscription-audit", agent_name="auto"),
        ],
    ),
    "lead-gen-pipeline": Pipeline(
        name="lead-gen-pipeline",
        description="Find hot leads on social platforms, qualify them, add to pipeline",
        steps=[
            PipelineStep(action="find-hot-leads", agent_name="growth", parameters={"platform": "twitter"}),
            PipelineStep(action="qualify-leads", agent_name="growth", input_mapping={"lead_url": "step_0.TOP_LEADS"}),
            PipelineStep(action="track-pipeline", agent_name="growth"),
        ],
    ),
    "nurture-convert-pipeline": Pipeline(
        name="nurture-convert-pipeline",
        description="Run outreach on qualified leads: LinkedIn connect, email follow-up, track results",
        steps=[
            PipelineStep(action="linkedin-outreach", agent_name="growth"),
            PipelineStep(action="email-outreach", agent_name="growth", input_mapping={"recipient_name": "step_0.PROSPECT_NAME"}),
            PipelineStep(action="track-pipeline", agent_name="growth"),
        ],
    ),
    "content-distribute-pipeline": Pipeline(
        name="content-distribute-pipeline",
        description="Post content across all channels: Twitter thread, LinkedIn post, then track engagement",
        steps=[
            PipelineStep(action="post-content", agent_name="growth", parameters={"platform": "twitter", "content_type": "thread"}),
            PipelineStep(action="post-content", agent_name="growth", parameters={"platform": "linkedin", "content_type": "post"}),
            PipelineStep(action="track-pipeline", agent_name="growth"),
        ],
    ),
    "weekly-growth-cycle": Pipeline(
        name="weekly-growth-cycle",
        description="Complete weekly growth cycle: find leads, qualify, outreach, post content, track pipeline",
        steps=[
            PipelineStep(action="find-hot-leads", agent_name="growth", parameters={"platform": "twitter"}),
            PipelineStep(action="qualify-leads", agent_name="growth", input_mapping={"lead_url": "step_0.TOP_LEADS"}),
            PipelineStep(action="linkedin-outreach", agent_name="growth"),
            PipelineStep(action="email-outreach", agent_name="growth"),
            PipelineStep(action="post-content", agent_name="growth", parameters={"platform": "twitter"}),
            PipelineStep(action="track-pipeline", agent_name="growth"),
        ],
    ),
}


# =========================================================================
# Manager Agent
# =========================================================================

class ManagerAgent:
    """Orchestrates multi-agent pipelines.

    The Manager doesn't execute browser tasks itself — it delegates
    to other agents via the AgentDispatcher, passing data between
    steps and handling failures.

    Usage:
        manager = ManagerAgent(dispatcher=dispatcher)

        # Run a built-in pipeline
        result = await manager.run_pipeline("full-saas-setup", {
            "project_name": "MyApp",
            "repo_name": "my-app",
        })

        # Run a custom pipeline
        pipeline = Pipeline(name="custom", description="...", steps=[...])
        result = await manager.run_custom_pipeline(pipeline, global_vars)

        # List available pipelines
        pipelines = manager.list_pipelines()
    """

    def __init__(self, dispatcher: AgentDispatcher) -> None:
        self._dispatcher = dispatcher
        self._pipelines: dict[str, Pipeline] = dict(BUILTIN_PIPELINES)
        self._status = AgentStatus.IDLE
        self._stats = {
            "total_pipelines": 0,
            "completed": 0,
            "failed": 0,
            "total_steps_executed": 0,
        }
        self._history: list[PipelineResult] = []

    # =========================================================================
    # BaseAgent Protocol (Manager is also an agent)
    # =========================================================================

    @property
    def name(self) -> str:
        return "manager"

    @property
    def description(self) -> str:
        return (
            "Orchestrates multi-agent pipelines — chains Research, Sales, "
            "Marketing, Finance, and DevOps agents into complex workflows."
        )

    @property
    def capabilities(self) -> list[AgentCapability]:
        return sorted([
            AgentCapability.BROWSER_AUTOMATION,
            AgentCapability.DATA_EXTRACTION,
            AgentCapability.FORM_FILLING,
            AgentCapability.ACCOUNT_SETUP,
            AgentCapability.DEPLOYMENT,
        ], key=lambda c: c.value)

    @property
    def status(self) -> AgentStatus:
        return self._status

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute a pipeline by name."""
        task_id = task.task_id or f"manager-{uuid4().hex[:12]}"

        if task.action not in self._pipelines:
            return AgentResult(
                task_id=task_id,
                agent_name=self.name,
                success=False,
                error=f"Pipeline '{task.action}' not found. Available: {', '.join(self._pipelines.keys())}",
            )

        pipeline_result = await self.run_pipeline(task.action, task.parameters, task.checkpoint_mode, task.headless)

        return AgentResult(
            task_id=task_id,
            agent_name=self.name,
            success=pipeline_result.success,
            data=pipeline_result.to_dict(),
            error=pipeline_result.error,
            duration_ms=pipeline_result.total_duration_ms,
        )

    def can_handle(self, action: str) -> bool:
        return action in self._pipelines

    def get_actions(self) -> list[dict[str, str]]:
        return [
            {"name": p.name, "description": p.description}
            for p in sorted(self._pipelines.values(), key=lambda p: p.name)
        ]

    def get_stats(self) -> dict[str, int]:
        return dict(self._stats)

    # =========================================================================
    # Pipeline Execution
    # =========================================================================

    async def run_pipeline(
        self,
        pipeline_name: str,
        global_variables: dict[str, str] | None = None,
        checkpoint_mode: str = "auto",
        headless: bool = True,
    ) -> PipelineResult:
        """Run a named pipeline with global variables.

        Global variables are merged into each step's parameters.
        Steps can also pull data from previous step results via input_mapping.
        """
        if pipeline_name not in self._pipelines:
            return PipelineResult(
                pipeline_name=pipeline_name,
                success=False,
                step_results=[],
                error=f"Pipeline '{pipeline_name}' not found",
            )

        pipeline = self._pipelines[pipeline_name]
        return await self.run_custom_pipeline(pipeline, global_variables, checkpoint_mode, headless)

    async def run_custom_pipeline(
        self,
        pipeline: Pipeline,
        global_variables: dict[str, str] | None = None,
        checkpoint_mode: str = "auto",
        headless: bool = True,
    ) -> PipelineResult:
        """Run a custom pipeline definition."""
        start_time = time.monotonic()
        self._status = AgentStatus.BUSY
        self._stats["total_pipelines"] += 1

        global_vars = global_variables or {}
        step_results: list[AgentResult] = []

        logger.info(
            "Starting pipeline",
            extra={
                "pipeline": pipeline.name,
                "steps": len(pipeline.steps),
            },
        )

        for i, step in enumerate(pipeline.steps):
            # Build step parameters: global vars + step params + mapped inputs
            params = {**global_vars, **step.parameters}

            # Resolve input mappings from previous step results
            for param_name, source in step.input_mapping.items():
                value = self._resolve_mapping(source, step_results)
                if value is not None:
                    params[param_name] = value

            # Check condition (if any)
            if step.condition and not self._evaluate_condition(step.condition, step_results):
                logger.info(f"Pipeline step {i} skipped — condition not met: {step.condition}")
                continue

            # Dispatch the task
            task = AgentTask(
                action=step.action,
                parameters=params,
                agent_name=step.agent_name if step.agent_name != "auto" else "",
                checkpoint_mode=checkpoint_mode,
                headless=headless,
                task_id=f"pipeline-{pipeline.name}-step-{i}",
            )

            try:
                result = await self._dispatcher.dispatch(task)
                step_results.append(result)
                self._stats["total_steps_executed"] += 1

                if not result.success:
                    logger.warning(
                        f"Pipeline step {i} failed",
                        extra={"action": step.action, "error": result.error},
                    )
                    # Continue to next step — don't abort on individual failures
                    # unless it's a critical step

            except Exception as e:
                logger.error(f"Pipeline step {i} raised exception: {e}")
                step_results.append(AgentResult(
                    task_id=task.task_id,
                    agent_name=step.agent_name,
                    success=False,
                    error=str(e),
                ))

        duration_ms = int((time.monotonic() - start_time) * 1000)
        all_success = all(r.success for r in step_results) if step_results else False

        if all_success:
            self._stats["completed"] += 1
        else:
            self._stats["failed"] += 1

        self._status = AgentStatus.IDLE

        pipeline_result = PipelineResult(
            pipeline_name=pipeline.name,
            success=all_success,
            step_results=step_results,
            total_duration_ms=duration_ms,
            error=None if all_success else "One or more steps failed",
        )

        self._history.append(pipeline_result)

        logger.info(
            "Pipeline completed",
            extra={
                "pipeline": pipeline.name,
                "success": all_success,
                "steps_completed": len([r for r in step_results if r.success]),
                "duration_ms": duration_ms,
            },
        )

        return pipeline_result

    # =========================================================================
    # Pipeline Management
    # =========================================================================

    def register_pipeline(self, pipeline: Pipeline) -> None:
        """Register a custom pipeline."""
        self._pipelines[pipeline.name] = pipeline

    def list_pipelines(self) -> list[dict[str, Any]]:
        """List all available pipelines."""
        return [
            {
                "name": p.name,
                "description": p.description,
                "steps": len(p.steps),
                "step_actions": [s.action for s in p.steps],
            }
            for p in sorted(self._pipelines.values(), key=lambda p: p.name)
        ]

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get pipeline execution history."""
        return [r.to_dict() for r in self._history[-limit:]]

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _resolve_mapping(self, source: str, step_results: list[AgentResult]) -> str | None:
        """Resolve a mapping like 'step_0.COMPANY_NAME' from previous results."""
        try:
            parts = source.split(".", 1)
            step_ref = parts[0]  # e.g., "step_0"
            var_name = parts[1] if len(parts) > 1 else ""

            step_index = int(step_ref.replace("step_", ""))
            if step_index >= len(step_results):
                return None

            result = step_results[step_index]
            # Look in extracted_variables first, then data
            extracted = result.data.get("extracted_variables", {})
            if isinstance(extracted, dict) and var_name in extracted:
                return extracted[var_name]

            return result.data.get(var_name)
        except (ValueError, IndexError, KeyError):
            return None

    def _evaluate_condition(self, condition: str, step_results: list[AgentResult]) -> bool:
        """Evaluate a simple condition like 'step_0.success == true'."""
        try:
            parts = condition.split(" == ")
            if len(parts) != 2:
                return True  # Can't parse — allow step to run

            source = parts[0].strip()
            expected = parts[1].strip().lower()

            if "success" in source:
                step_ref = source.split(".")[0]
                step_index = int(step_ref.replace("step_", ""))
                if step_index >= len(step_results):
                    return False
                actual = str(step_results[step_index].success).lower()
                return actual == expected

            return True
        except Exception:
            return True  # On error, allow step to run

    def get_lessons(self) -> list[dict[str, Any]]:
        """Return failed pipeline executions as lessons."""
        return [r.to_dict() for r in self._history if not r.success]
