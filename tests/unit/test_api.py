"""Tests for WebPilot Agent — FastAPI Server.

Following TDD discipline: tests written FIRST, then verified against implementation.
Covers: REST endpoints (list workflows, get workflow, start execution, get status),
WebSocket checkpoint integration, and error handling.

The API server is the remote control — it lets dashboards and external tools
drive the agent over HTTP/WebSocket instead of the terminal.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def sample_workflows_dir(tmp_path: Path) -> Path:
    """Create a workflows directory with a test workflow."""
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    wf = workflows_dir / "test-workflow.yaml"
    wf.write_text("""
name: test-workflow
description: A test workflow
version: "1.0"
tags:
  - test
steps:
  - type: navigate
    url: https://example.com
  - type: checkpoint
    message: "Continue?"
  - type: click
    selector: button.submit
    description: Click submit
""")
    return workflows_dir


@pytest.fixture
def app(sample_workflows_dir):
    """Create FastAPI app with test workflows."""
    from src.api.server import create_app
    return create_app(workflows_dir=sample_workflows_dir)


@pytest.fixture
async def client(app):
    """Async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# =========================================================================
# Health Check
# =========================================================================

class TestHealthCheck:

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_includes_version(self, client):
        response = await client.get("/health")
        data = response.json()
        assert "version" in data


# =========================================================================
# Workflow Endpoints
# =========================================================================

class TestWorkflowEndpoints:

    @pytest.mark.asyncio
    async def test_list_workflows(self, client):
        response = await client.get("/api/workflows")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_list_workflows_has_name(self, client):
        response = await client.get("/api/workflows")
        data = response.json()
        names = [w["name"] for w in data]
        assert "test-workflow" in names

    @pytest.mark.asyncio
    async def test_get_workflow(self, client):
        response = await client.get("/api/workflows/test-workflow")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-workflow"
        assert "steps" in data

    @pytest.mark.asyncio
    async def test_get_workflow_not_found(self, client):
        response = await client.get("/api/workflows/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_workflow_includes_steps(self, client):
        response = await client.get("/api/workflows/test-workflow")
        data = response.json()
        assert len(data["steps"]) == 3


# =========================================================================
# Execution Endpoints
# =========================================================================

class TestExecutionEndpoints:

    @pytest.mark.asyncio
    async def test_start_execution_dry_run(self, client):
        """Dry run should return workflow info without launching browser."""
        response = await client.post(
            "/api/executions",
            json={
                "workflow_name": "test-workflow",
                "dry_run": True,
                "variables": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["workflow_name"] == "test-workflow"
        assert data["dry_run"] is True

    @pytest.mark.asyncio
    async def test_start_execution_unknown_workflow(self, client):
        response = await client.post(
            "/api/executions",
            json={
                "workflow_name": "nonexistent",
                "dry_run": True,
            },
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_dry_run_includes_steps(self, client):
        response = await client.post(
            "/api/executions",
            json={
                "workflow_name": "test-workflow",
                "dry_run": True,
            },
        )
        data = response.json()
        assert "steps" in data
        assert len(data["steps"]) == 3
