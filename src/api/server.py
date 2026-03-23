"""WebPilot Agent — FastAPI Server.

REST API + WebSocket server for driving the agent remotely.
This is the "remote control" — dashboards and external tools use HTTP
to list workflows, start executions, and approve checkpoints.

Endpoints:
  GET  /health                    Health check
  GET  /api/workflows             List all workflows
  GET  /api/workflows/{name}      Get a specific workflow
  POST /api/executions            Start a workflow execution (live or dry-run)
  GET  /api/executions/{id}       Get execution result
  GET  /api/executions            List execution history
  GET  /api/agents                List registered agents
  GET  /api/agents/{name}         Get agent details
  POST /api/agents/{name}/execute Execute a task on a specific agent
  WS   /ws/checkpoints/{id}       WebSocket for checkpoint approvals

Patterns applied:
- FastAPI for async-first REST + WebSocket
- Pydantic for request/response validation
- Dependency injection for registry, vault, executor
- Multi-agent dispatch via AgentDispatcher
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from src.agents.base import AgentRegistry, AgentTask
from src.agents.devops_setup import DevOpsSetupAgent
from src.agents.dispatcher import AgentDispatcher, DispatchError
from src.core.models import CheckpointResult
from src.core.workflow_registry import WorkflowRegistry, WorkflowNotFoundError

logger = logging.getLogger(__name__)

__version__ = "0.2.0"


# =========================================================================
# Request/Response Models
# =========================================================================

class ExecutionRequest(BaseModel):
    """Request to start a workflow execution."""
    workflow_name: str
    variables: dict[str, str] = Field(default_factory=dict)
    dry_run: bool = False
    checkpoint_mode: str = "auto"
    headless: bool = True


class AgentExecutionRequest(BaseModel):
    """Request to execute a task on a specific agent."""
    action: str
    parameters: dict[str, str] = Field(default_factory=dict)
    checkpoint_mode: str = "auto"
    headless: bool = True


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
    agents: int = 0


# =========================================================================
# WebSocket Checkpoint State
# =========================================================================

# Active WebSocket connections for checkpoint approvals
_checkpoint_connections: dict[str, WebSocket] = {}
_checkpoint_responses: dict[str, asyncio.Future] = {}


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
        description="Multi-agent browser automation with human-in-the-loop checkpoints",
        version=__version__,
    )

    # Initialize workflow registry
    wf_dir = workflows_dir or Path("./workflows")
    registry = WorkflowRegistry(workflows_dir=wf_dir)
    registry.load_all()

    # Initialize agent system
    agent_registry = AgentRegistry()
    devops_agent = DevOpsSetupAgent(workflows_dir=wf_dir)
    agent_registry.register(devops_agent)

    dispatcher = AgentDispatcher(registry=agent_registry)

    # Store in app state
    app.state.registry = registry
    app.state.agent_registry = agent_registry
    app.state.dispatcher = dispatcher

    # ── Health ──

    @app.get("/health", response_model=HealthResponse)
    async def health():
        return HealthResponse(agents=agent_registry.count)

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

        # Live execution via agent dispatcher
        task = AgentTask(
            action=request.workflow_name,
            parameters=request.variables,
            checkpoint_mode=request.checkpoint_mode,
            headless=request.headless,
        )

        try:
            result = await dispatcher.dispatch(task)
            return result.to_dict()
        except DispatchError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/executions/{task_id}")
    async def get_execution(task_id: str):
        """Get the result of a completed or pending execution."""
        # Check if still pending
        if dispatcher.is_pending(task_id):
            return {
                "task_id": task_id,
                "status": "running",
                "message": "Execution is still in progress",
            }

        # Check completed results
        result = dispatcher.get_result(task_id)
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Execution '{task_id}' not found",
            )

        return result.to_dict()

    @app.get("/api/executions")
    async def list_executions(
        agent_name: str | None = None,
        limit: int = 50,
    ):
        """List execution history."""
        return dispatcher.get_history(agent_name=agent_name, limit=limit)

    # ── Agents ──

    @app.get("/api/agents")
    async def list_agents():
        """List all registered agents with capabilities."""
        return agent_registry.list_agents()

    @app.get("/api/agents/{name}")
    async def get_agent(name: str):
        """Get details for a specific agent."""
        try:
            agent = agent_registry.get(name)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail=f"Agent '{name}' not found",
            )

        return {
            "name": agent.name,
            "description": agent.description,
            "status": agent.status.value,
            "capabilities": [c.value for c in agent.capabilities],
            "actions": agent.get_actions(),
            "stats": agent.get_stats(),
        }

    @app.post("/api/agents/{name}/execute")
    async def execute_on_agent(name: str, request: AgentExecutionRequest):
        """Execute a task on a specific named agent."""
        task = AgentTask(
            action=request.action,
            parameters=request.parameters,
            agent_name=name,
            checkpoint_mode=request.checkpoint_mode,
            headless=request.headless,
        )

        try:
            result = await dispatcher.dispatch_to(name, task)
            return result.to_dict()
        except DispatchError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # ── WebSocket Checkpoints ──

    @app.websocket("/ws/checkpoints/{execution_id}")
    async def checkpoint_websocket(websocket: WebSocket, execution_id: str):
        """WebSocket endpoint for real-time checkpoint approvals.

        Protocol:
          1. Client connects to /ws/checkpoints/{execution_id}
          2. Server pushes checkpoint events as JSON:
             {"type": "checkpoint", "step_index": N, "message": "...", "screenshot_b64": "..."}
          3. Client responds with approval:
             {"approved": true/false, "reason": "optional reason"}
          4. Server resumes workflow execution
        """
        await websocket.accept()
        _checkpoint_connections[execution_id] = websocket

        logger.info(
            "WebSocket checkpoint connection established",
            extra={"execution_id": execution_id},
        )

        try:
            while True:
                # Wait for client messages (approval responses)
                data = await websocket.receive_json()

                approved = data.get("approved", False)
                reason = data.get("reason")

                # Resolve any pending checkpoint future
                future = _checkpoint_responses.get(execution_id)
                if future and not future.done():
                    result = CheckpointResult(
                        approved=approved,
                        by="websocket",
                        reason=reason,
                    )
                    future.set_result(result)

        except WebSocketDisconnect:
            logger.info(
                "WebSocket checkpoint connection closed",
                extra={"execution_id": execution_id},
            )
        finally:
            _checkpoint_connections.pop(execution_id, None)
            _checkpoint_responses.pop(execution_id, None)

    # ── Dispatcher Stats ──

    @app.get("/api/stats")
    async def get_stats():
        """Get system-wide statistics."""
        return {
            "dispatcher": dispatcher.get_stats(),
            "agents": {
                agent.name: agent.get_stats()
                for agent in [
                    agent_registry.get(name)
                    for name in agent_registry.names
                ]
            },
            "workflows": {
                "total": registry.count,
                "names": registry.names,
            },
        }

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
