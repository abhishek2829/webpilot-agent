"""Tests for WebPilot Agent — Workflow Executor.

Following TDD discipline: tests written FIRST, then verified against implementation.
Covers: step-by-step execution, checkpoint integration, variable extraction,
recovery delegation, execution results, compound-engineering, and edge cases.

The Workflow Executor is the central nervous system — the main loop that:
  1. Loads a workflow from the registry
  2. Resolves variables
  3. Iterates through steps
  4. Calls ActionEngine for browser steps
  5. Calls CheckpointManager for checkpoint steps
  6. Delegates errors to RecoveryEngine
  7. Produces an ExecutionResult

Analogy: An orchestra conductor. The instruments (browser, LLM, checkpoints)
are all warmed up and ready. The conductor reads the score (workflow YAML),
cues each instrument in turn, handles mistakes (recovery), and knows when
to ask the audience (human) for permission to continue.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.core.models import (
    CheckpointResult,
    ExecutionResult,
    ExecutionStatus,
    Step,
    StepResult,
    StepType,
    Workflow,
    FallbackStrategy,
)
from src.browser.actions import ActionError, ActionResult


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def simple_workflow() -> Workflow:
    """A minimal workflow: navigate → click → extract."""
    return Workflow(
        name="test-workflow",
        description="A simple test workflow",
        steps=[
            Step(type=StepType.NAVIGATE, url="https://example.com"),
            Step(type=StepType.CLICK, selector="button.submit", description="Click submit"),
            Step(
                type=StepType.EXTRACT,
                selector=".api-key",
                variable="API_KEY",
                description="Extract API key",
            ),
        ],
    )


@pytest.fixture
def workflow_with_checkpoint() -> Workflow:
    """Workflow with a checkpoint step in the middle."""
    return Workflow(
        name="checkpoint-workflow",
        description="Workflow with human checkpoint",
        steps=[
            Step(type=StepType.NAVIGATE, url="https://example.com"),
            Step(
                type=StepType.CHECKPOINT,
                message="Confirm before proceeding?",
                screenshot=True,
            ),
            Step(type=StepType.CLICK, selector="button.submit", description="Click submit"),
        ],
    )


@pytest.fixture
def workflow_with_variables() -> Workflow:
    """Workflow that uses variable substitution."""
    return Workflow(
        name="var-workflow",
        description="Workflow with variables",
        variables={"project_name": "DefaultApp"},
        steps=[
            Step(type=StepType.NAVIGATE, url="https://example.com"),
            Step(
                type=StepType.TYPE,
                selector="input[name='name']",
                text="{{project_name}}",
                description="Type project name",
            ),
        ],
    )


@pytest.fixture
def mock_session():
    """Mock browser session."""
    session = AsyncMock()
    session.start = AsyncMock()
    session.close = AsyncMock()
    session.page = AsyncMock()
    session.screenshot = AsyncMock(return_value=b"fake-screenshot")
    session.save_state = AsyncMock()
    return session


@pytest.fixture
def mock_action_engine():
    """Mock action engine that succeeds on all steps."""
    engine = AsyncMock()
    engine.execute = AsyncMock(
        return_value=ActionResult(success=True, duration_ms=50)
    )
    return engine


@pytest.fixture
def mock_checkpoint_manager():
    """Mock checkpoint manager that approves everything."""
    mgr = AsyncMock()
    mgr.request_approval = AsyncMock(
        return_value=CheckpointResult(approved=True, by="user")
    )
    return mgr


@pytest.fixture
def mock_recovery_engine():
    """Mock recovery engine."""
    from src.core.recovery import RecoveryResult

    engine = AsyncMock()
    engine.handle = AsyncMock(
        return_value=RecoveryResult(resolved=True, strategy_used="retry")
    )
    return engine


# =========================================================================
# Basic Execution
# =========================================================================

class TestBasicExecution:
    """Test the happy path: workflow runs start to finish."""

    @pytest.mark.asyncio
    async def test_execute_simple_workflow(
        self, simple_workflow, mock_session, mock_action_engine,
        mock_checkpoint_manager, mock_recovery_engine
    ):
        from src.core.executor import WorkflowExecutor

        executor = WorkflowExecutor(
            action_engine=mock_action_engine,
            checkpoint_manager=mock_checkpoint_manager,
            recovery_engine=mock_recovery_engine,
        )

        result = await executor.execute(
            workflow=simple_workflow,
            session=mock_session,
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert result.workflow_name == "test-workflow"

    @pytest.mark.asyncio
    async def test_executes_all_steps(
        self, simple_workflow, mock_session, mock_action_engine,
        mock_checkpoint_manager, mock_recovery_engine
    ):
        from src.core.executor import WorkflowExecutor

        executor = WorkflowExecutor(
            action_engine=mock_action_engine,
            checkpoint_manager=mock_checkpoint_manager,
            recovery_engine=mock_recovery_engine,
        )

        result = await executor.execute(
            workflow=simple_workflow,
            session=mock_session,
        )

        # 3 steps = 3 action engine calls (navigate, click, extract)
        assert mock_action_engine.execute.call_count == 3
        assert len(result.step_results) == 3

    @pytest.mark.asyncio
    async def test_execution_has_id(
        self, simple_workflow, mock_session, mock_action_engine,
        mock_checkpoint_manager, mock_recovery_engine
    ):
        from src.core.executor import WorkflowExecutor

        executor = WorkflowExecutor(
            action_engine=mock_action_engine,
            checkpoint_manager=mock_checkpoint_manager,
            recovery_engine=mock_recovery_engine,
        )

        result = await executor.execute(
            workflow=simple_workflow,
            session=mock_session,
        )

        assert result.id is not None
        assert len(result.id) > 0

    @pytest.mark.asyncio
    async def test_execution_has_timing(
        self, simple_workflow, mock_session, mock_action_engine,
        mock_checkpoint_manager, mock_recovery_engine
    ):
        from src.core.executor import WorkflowExecutor

        executor = WorkflowExecutor(
            action_engine=mock_action_engine,
            checkpoint_manager=mock_checkpoint_manager,
            recovery_engine=mock_recovery_engine,
        )

        result = await executor.execute(
            workflow=simple_workflow,
            session=mock_session,
        )

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.total_duration_ms >= 0


# =========================================================================
# Checkpoint Handling
# =========================================================================

class TestCheckpointHandling:
    """Test checkpoint steps pause and wait for human approval."""

    @pytest.mark.asyncio
    async def test_checkpoint_step_calls_manager(
        self, workflow_with_checkpoint, mock_session, mock_action_engine,
        mock_checkpoint_manager, mock_recovery_engine
    ):
        from src.core.executor import WorkflowExecutor

        executor = WorkflowExecutor(
            action_engine=mock_action_engine,
            checkpoint_manager=mock_checkpoint_manager,
            recovery_engine=mock_recovery_engine,
        )

        await executor.execute(
            workflow=workflow_with_checkpoint,
            session=mock_session,
        )

        mock_checkpoint_manager.request_approval.assert_called_once()

    @pytest.mark.asyncio
    async def test_checkpoint_approved_continues(
        self, workflow_with_checkpoint, mock_session, mock_action_engine,
        mock_checkpoint_manager, mock_recovery_engine
    ):
        from src.core.executor import WorkflowExecutor

        mock_checkpoint_manager.request_approval = AsyncMock(
            return_value=CheckpointResult(approved=True, by="user")
        )

        executor = WorkflowExecutor(
            action_engine=mock_action_engine,
            checkpoint_manager=mock_checkpoint_manager,
            recovery_engine=mock_recovery_engine,
        )

        result = await executor.execute(
            workflow=workflow_with_checkpoint,
            session=mock_session,
        )

        assert result.status == ExecutionStatus.COMPLETED
        # Navigate + Click = 2 action calls (checkpoint is not an action)
        assert mock_action_engine.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_checkpoint_rejected_aborts(
        self, workflow_with_checkpoint, mock_session, mock_action_engine,
        mock_checkpoint_manager, mock_recovery_engine
    ):
        from src.core.executor import WorkflowExecutor

        mock_checkpoint_manager.request_approval = AsyncMock(
            return_value=CheckpointResult(approved=False, by="user", reason="Not ready")
        )

        executor = WorkflowExecutor(
            action_engine=mock_action_engine,
            checkpoint_manager=mock_checkpoint_manager,
            recovery_engine=mock_recovery_engine,
        )

        result = await executor.execute(
            workflow=workflow_with_checkpoint,
            session=mock_session,
        )

        assert result.status == ExecutionStatus.ABORTED
        # Only navigate ran, click after checkpoint should NOT have been called
        assert mock_action_engine.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_checkpoint_takes_screenshot(
        self, workflow_with_checkpoint, mock_session, mock_action_engine,
        mock_checkpoint_manager, mock_recovery_engine
    ):
        from src.core.executor import WorkflowExecutor

        executor = WorkflowExecutor(
            action_engine=mock_action_engine,
            checkpoint_manager=mock_checkpoint_manager,
            recovery_engine=mock_recovery_engine,
        )

        await executor.execute(
            workflow=workflow_with_checkpoint,
            session=mock_session,
        )

        # Session.screenshot() should be called for the checkpoint
        mock_session.screenshot.assert_called()


# =========================================================================
# Variable Extraction
# =========================================================================

class TestVariableExtraction:
    """Test that extracted values are stored in the execution result."""

    @pytest.mark.asyncio
    async def test_extracted_values_in_result(
        self, mock_session, mock_checkpoint_manager, mock_recovery_engine
    ):
        from src.core.executor import WorkflowExecutor

        workflow = Workflow(
            name="extract-test",
            description="Test extraction",
            steps=[
                Step(type=StepType.NAVIGATE, url="https://example.com"),
                Step(
                    type=StepType.EXTRACT,
                    selector=".key",
                    variable="MY_KEY",
                    description="Extract key",
                ),
            ],
        )

        mock_engine = AsyncMock()
        # First call: navigate (no extraction)
        # Second call: extract (returns extracted value)
        mock_engine.execute = AsyncMock(
            side_effect=[
                ActionResult(success=True, duration_ms=50),
                ActionResult(success=True, duration_ms=50, extracted_value="pk_live_abc123"),
            ]
        )

        executor = WorkflowExecutor(
            action_engine=mock_engine,
            checkpoint_manager=mock_checkpoint_manager,
            recovery_engine=mock_recovery_engine,
        )

        result = await executor.execute(workflow=workflow, session=mock_session)

        assert result.extracted_variables.get("MY_KEY") == "pk_live_abc123"


# =========================================================================
# Variable Substitution
# =========================================================================

class TestVariableSubstitution:
    """Test that {{variables}} are resolved before execution."""

    @pytest.mark.asyncio
    async def test_variables_resolved(
        self, workflow_with_variables, mock_session, mock_action_engine,
        mock_checkpoint_manager, mock_recovery_engine
    ):
        from src.core.executor import WorkflowExecutor

        executor = WorkflowExecutor(
            action_engine=mock_action_engine,
            checkpoint_manager=mock_checkpoint_manager,
            recovery_engine=mock_recovery_engine,
        )

        result = await executor.execute(
            workflow=workflow_with_variables,
            session=mock_session,
            variables={"project_name": "MyApp"},
        )

        assert result.status == ExecutionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_user_variables_override_defaults(
        self, workflow_with_variables, mock_session, mock_action_engine,
        mock_checkpoint_manager, mock_recovery_engine
    ):
        from src.core.executor import WorkflowExecutor

        executor = WorkflowExecutor(
            action_engine=mock_action_engine,
            checkpoint_manager=mock_checkpoint_manager,
            recovery_engine=mock_recovery_engine,
        )

        # Call with user override
        await executor.execute(
            workflow=workflow_with_variables,
            session=mock_session,
            variables={"project_name": "CustomName"},
        )

        # Check the step that was passed to action engine had resolved text
        call_args = mock_action_engine.execute.call_args_list
        # Second call is the TYPE step
        type_step = call_args[1][1].get("step") or call_args[1][0][1]
        assert type_step.text == "CustomName"


# =========================================================================
# Error Handling & Recovery
# =========================================================================

class TestErrorHandling:
    """Test that errors are delegated to the recovery engine."""

    @pytest.mark.asyncio
    async def test_action_error_delegates_to_recovery(
        self, simple_workflow, mock_session, mock_checkpoint_manager, mock_recovery_engine
    ):
        from src.core.executor import WorkflowExecutor
        from src.core.recovery import RecoveryResult

        # First step succeeds, second step fails
        failing_engine = AsyncMock()
        failing_engine.execute = AsyncMock(
            side_effect=[
                ActionResult(success=True, duration_ms=50),
                ActionError(simple_workflow.steps[1], "Click failed"),
                ActionResult(success=True, duration_ms=50),  # after recovery
            ]
        )

        mock_recovery_engine.handle = AsyncMock(
            return_value=RecoveryResult(resolved=True, strategy_used="retry")
        )

        executor = WorkflowExecutor(
            action_engine=failing_engine,
            checkpoint_manager=mock_checkpoint_manager,
            recovery_engine=mock_recovery_engine,
        )

        result = await executor.execute(
            workflow=simple_workflow,
            session=mock_session,
        )

        mock_recovery_engine.handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_unrecoverable_error_fails_execution(
        self, simple_workflow, mock_session, mock_checkpoint_manager
    ):
        from src.core.executor import WorkflowExecutor
        from src.core.recovery import RecoveryResult

        failing_engine = AsyncMock()
        failing_engine.execute = AsyncMock(
            side_effect=ActionError(simple_workflow.steps[0], "Fatal error")
        )

        unrecoverable = AsyncMock()
        unrecoverable.handle = AsyncMock(
            return_value=RecoveryResult(resolved=False, strategy_used="exhausted", error="All strategies failed")
        )

        executor = WorkflowExecutor(
            action_engine=failing_engine,
            checkpoint_manager=mock_checkpoint_manager,
            recovery_engine=unrecoverable,
        )

        result = await executor.execute(
            workflow=simple_workflow,
            session=mock_session,
        )

        assert result.status == ExecutionStatus.FAILED
        assert result.error is not None


# =========================================================================
# Compound Engineering
# =========================================================================

class TestExecutorCompoundEngineering:
    """Execution stats and lessons tracked."""

    @pytest.mark.asyncio
    async def test_execution_stats(
        self, simple_workflow, mock_session, mock_action_engine,
        mock_checkpoint_manager, mock_recovery_engine
    ):
        from src.core.executor import WorkflowExecutor

        executor = WorkflowExecutor(
            action_engine=mock_action_engine,
            checkpoint_manager=mock_checkpoint_manager,
            recovery_engine=mock_recovery_engine,
        )

        await executor.execute(workflow=simple_workflow, session=mock_session)

        stats = executor.get_stats()
        assert stats["total_executions"] == 1
        assert stats["completed"] == 1

    @pytest.mark.asyncio
    async def test_failed_execution_in_stats(
        self, simple_workflow, mock_session, mock_checkpoint_manager
    ):
        from src.core.executor import WorkflowExecutor
        from src.core.recovery import RecoveryResult

        failing_engine = AsyncMock()
        failing_engine.execute = AsyncMock(
            side_effect=ActionError(simple_workflow.steps[0], "Fatal")
        )

        unrecoverable = AsyncMock()
        unrecoverable.handle = AsyncMock(
            return_value=RecoveryResult(resolved=False, strategy_used="exhausted", error="Failed")
        )

        executor = WorkflowExecutor(
            action_engine=failing_engine,
            checkpoint_manager=mock_checkpoint_manager,
            recovery_engine=unrecoverable,
        )

        await executor.execute(workflow=simple_workflow, session=mock_session)

        stats = executor.get_stats()
        assert stats["failed"] == 1

    @pytest.mark.asyncio
    async def test_get_lessons_from_failures(
        self, simple_workflow, mock_session, mock_checkpoint_manager
    ):
        from src.core.executor import WorkflowExecutor
        from src.core.recovery import RecoveryResult

        failing_engine = AsyncMock()
        failing_engine.execute = AsyncMock(
            side_effect=ActionError(simple_workflow.steps[0], "Fatal")
        )

        unrecoverable = AsyncMock()
        unrecoverable.handle = AsyncMock(
            return_value=RecoveryResult(resolved=False, strategy_used="exhausted", error="Failed")
        )

        executor = WorkflowExecutor(
            action_engine=failing_engine,
            checkpoint_manager=mock_checkpoint_manager,
            recovery_engine=unrecoverable,
        )

        await executor.execute(workflow=simple_workflow, session=mock_session)

        lessons = executor.get_lessons()
        assert len(lessons) >= 1
