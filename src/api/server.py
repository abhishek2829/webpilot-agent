"""WebPilot Agent — FastAPI Server.

REST API + WebSocket server for driving the agent remotely.
This is the "remote control" — dashboards and external tools use HTTP
to list workflows, start executions, and approve checkpoints.

Endpoints:
  GET  /health                  Health check
  GET  /api/workflows           List all workflows
  GET  /api/workflows/{name}    Get a specific workflow
  POST /api/executions          Start a workflow execution
  GET  /api/executions/{id}     Get execution status (TODO)
  WS   /ws/checkpoints/{id}     WebSocket for checkpoint approvals (TODO)

Patterns applied:
- FastAPI for async-first REST + WebSocket
- Pydantic for request/response validation
- Dependency injection for registry, vault, executor
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.core.workflow_registry import WorkflowRegistry, WorkflowNotFoundError

logger = logging.getLogger(__name__)

__version__ = "0.1.0"


# =========================================================================
# Request/Response Models
# =========================================================================

class ExecutionRequest(BaseModel):
    """Request to start a workflow execution."""
    workflow_name: str
    variables: dict[str, str] = Field(default_factory=dict)
    dry_run: bool = False
    checkpoint_mode: str = "cli"


class WorkflowResponse(BaseModel):
    """Workflow details for API response."""
    name: str
    description: str
    version: str
    tags: list[str]
    steps: list[dict[str, Any]]
    variables: dict[str, str]
    credentials_required: list[str]


class DryRunResponse(BaseModel):
    """Response for a dry-run execution."""
    workflow_name: str
    dry_run: bool = True
    steps: list[dict[str, Any]]
    variables: dict[str, str]
    checkpoint_count: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str = __version__


# =========================================================================
# App Factory
# =========================================================================

def create_app(workflows_dir: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Uses a factory pattern so tests can inject their own workflows directory.

    Args:
        workflows_dir: Path to workflow YAML files. Defaults to ./workflows.

    Returns:
        Configured FastAPI app instance.
    """
    app = FastAPI(
        title="WebPilot Agent API",
        description="Semi-autonomous browser agent with human-in-the-loop checkpoints",
        version=__version__,
    )

    # Initialize registry
    wf_dir = workflows_dir or Path("./workflows")
    registry = WorkflowRegistry(workflows_dir=wf_dir)
    registry.load_all()

    # Store in app state for dependency access
    app.state.registry = registry

    # ── Health ──

    @app.get("/health", response_model=HealthResponse)
    async def health():
        return HealthResponse()

    # ── Workflows ──

    @app.get("/api/workflows")
    async def list_workflows():
        return registry.list_workflows()

    @app.get("/api/workflows/{name}")
    async def get_workflow(name: str):
        try:
            wf = registry.get(name)
        except WorkflowNotFoundError:
            raise HTTPException(status_code=404, detail=f"Workflow '{name}' not found")

        return WorkflowResponse(
            name=wf.name,
            description=wf.description,
            version=wf.version,
            tags=wf.tags,
            steps=[step.model_dump() for step in wf.steps],
            variables=wf.variables,
            credentials_required=wf.credentials_required,
        )

    # ── Executions ──

    @app.post("/api/executions")
    async def start_execution(request: ExecutionRequest):
        try:
            wf = registry.get(request.workflow_name)
        except WorkflowNotFoundError:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow '{request.workflow_name}' not found",
            )

        if request.dry_run:
            resolved = wf.resolved_steps(request.variables)
            return DryRunResponse(
                workflow_name=wf.name,
                steps=[
                    {
                        "index": i,
                        "type": step.type.value,
                        "description": step.description or step.url or step.selector or step.message or step.type.value,
                    }
                    for i, step in enumerate(resolved)
                ],
                variables={**wf.variables, **request.variables},
                checkpoint_count=wf.checkpoint_count(),
            )

        # TODO: Real execution — launch browser, run workflow, return execution ID
        # For now, this requires the CLI or direct Python usage
        raise HTTPException(
            status_code=501,
            detail="Live execution via API coming in Sprint 5. Use CLI for now: webpilot run",
        )

    return app


# =========================================================================
# Entry Point
# =========================================================================

def start_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Start the uvicorn server."""
    import uvicorn
    app = create_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
