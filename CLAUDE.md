# WebPilot Agent — CLAUDE.md

> **For Claude Code:** This file provides all context needed to continue building this project.
> Read this FIRST before doing any work.

## Project Overview

**WebPilot Agent** is a semi-autonomous browser agent that executes multi-step web workflows (SaaS setup, data extraction, form filling) with human-in-the-loop checkpoints. Built for personal use AND productization as a paid service.

**First workflow:** Clerk authentication setup (navigate → create app → configure auth → extract API keys).

**This becomes the DevOps Setup Agent** in Abhishek's Multi-Agent System.

## Current State

**Sprint 1: Foundation — COMPLETE (4/4 tasks, 78 tests)**
- Task 1: Project bootstrap + config (`src/core/config.py`)
- Task 2: Domain models (`src/core/models.py`) — Workflow, Step, StepType, CheckpointEvent, ExecutionResult
- Task 3: Credential vault (`src/credentials/vault.py`) — Fernet encryption, 31 tests
- Task 4: Workflow registry (`src/core/workflow_registry.py`) — YAML loading, validation, search, pre-flight checks, 47 tests

**Sprint 2: Browser Engine — COMPLETE (3/3 tasks, 27 tests)**
- Task 5: Browser session manager (`src/browser/session.py`) — Playwright lifecycle, state persistence, screenshots
- Task 6: Action engine (`src/browser/actions.py`) — 8 action types, two-tier element finding (CSS → LLM vision), retry logic, selector analytics
- Task 7: LLM brain (`src/core/llm_brain.py`) — Claude vision: find_element, extract_value, understand_page

**Sprint 3: Orchestration — COMPLETE (3/3 tasks, 64 tests)**
- Task 8: Checkpoint manager (`src/checkpoints/manager.py`) — CLI + WebSocket + auto-approve modes, 32 tests
- Task 9: Workflow executor (`src/core/executor.py`) — Central loop: step iteration, checkpoint delegation, variable extraction, recovery delegation, 16 tests
- Task 10: Recovery engine (`src/core/recovery.py`) — Three-tier: retry → LLM adapt → escalate to checkpoint, 16 tests

**Sprint 4: Interfaces — COMPLETE (3/3 tasks, 39 tests)**
- Task 11: CLI (`src/cli/main.py`) — Typer CLI: `webpilot run` (with --dry-run), `webpilot list`, `webpilot creds set/get/list/delete`, 16 tests
- Task 12: FastAPI server (`src/api/server.py`) — REST API: health, list/get workflows, start executions (dry-run), 10 tests
- Task 13: Database layer (`src/core/database.py`) — SQLAlchemy async + SQLite, execution history CRUD, 13 tests

**Sprint 5: Production Hardening — COMPLETE (4/4 tasks, 135 tests)**
- Task 14: Task queue (`src/tasks/queue.py`) — InMemoryTaskQueue with TaskStatus lifecycle, WorkflowTask/TaskResult models, Celery-ready protocol, 20 tests
- Task 15: Structured logging (`src/core/logging.py`) — structlog JSON/console output, SensitiveDataFilter, ExecutionLogger with stats/lessons, 28 tests
- Task 16: Security hardening (`src/security/middleware.py`) — API key auth, rate limiting, input sanitization, security headers, 22 tests
- Task 17: Full test coverage — 84.25% (80%+ target), mock-based browser/session/action tests, config tests, 65 additional tests

**Total: 17/17 tasks complete, 278+ tests passing, 84% coverage**

**Phase 4: Workflow Library & Infrastructure — COMPLETE (4/4 tasks, 114 tests)**
- Task 18: Workflow library — 5 pre-built YAML workflows (vercel-deploy, supabase-setup, stripe-setup, github-repo, domain-setup), 100 tests
- Task 19: PostgreSQL migration — Alembic setup with async support, initial migration (`alembic/versions/001_initial_schema.py`)
- Task 20: Celery + Redis workers — CeleryTaskQueue implementing TaskQueue protocol, worker tasks, celery app config, 14 tests
- Task 21: Docker Compose — PostgreSQL 16 + Redis 7 infrastructure (`docker-compose.yml`)

**Grand total: 21/21 tasks complete, 392+ tests, 6 workflows**

**Phase 5: Multi-Agent System Integration — COMPLETE (6/6 tasks, 54 tests)**
- Task 22: BaseAgent protocol + AgentRegistry (`src/agents/base.py`) — Protocol with capabilities, status, actions; registry with discovery and search
- Task 23: DevOpsSetupAgent (`src/agents/devops_setup.py`) — First concrete agent wrapping the WebPilot executor, handles all 6 workflows
- Task 24: AgentDispatcher (`src/agents/dispatcher.py`) — Routes tasks to agents, stores results, tracks execution history
- Task 25: API v2 (`src/api/server.py`) — Live execution (POST /api/executions), execution status (GET /api/executions/{id}), agent endpoints, WebSocket checkpoints, stats
- Task 26: BrowserSessionPool (`src/browser/session_pool.py`) — Reusable session pool with lazy creation, idle cleanup, max capacity enforcement
- Task 27: Multi-agent tests — 54 tests covering BaseAgent, AgentRegistry, DevOpsSetupAgent, AgentDispatcher, BrowserSessionPool

**Grand total: 27/27 tasks complete, 446+ tests, 6 workflows, 1 agent**

**Phase 6: Full Agent Fleet — COMPLETE (7/7 tasks, 44 tests, 20 new workflows)**
- Task 28: ResearchAgent (`src/agents/research.py`) + 5 workflows (competitor-analysis, lead-research, market-validation, tech-stack-detect, content-research)
- Task 29: SalesAgent (`src/agents/sales.py`) + 5 workflows (linkedin-connect, crm-entry, email-campaign, meeting-setup, proposal-gen)
- Task 30: MarketingAgent (`src/agents/marketing.py`) + 5 workflows (social-post, seo-audit, blog-outline, newsletter-setup, analytics-report)
- Task 31: FinanceAgent (`src/agents/finance.py`) + 5 workflows (invoice-tracker, payment-monitor, expense-report, subscription-audit, revenue-dashboard)
- Task 32: ManagerAgent (`src/agents/manager.py`) — Pipeline orchestrator with 4 built-in pipelines (full-saas-setup, outbound-pipeline, content-launch, revenue-health-check)
- Task 33: API v3 — All 6 agents registered, pipeline endpoints (GET /api/pipelines, POST /api/pipelines/{name}/run)
- Task 34: Full fleet tests — 44 tests covering all agents, registry, dispatcher, pipelines

**Grand total: 34/34 tasks complete, 490+ tests, 26 workflows, 6 agents, 4 pipelines**

## What to Build Next

**Future enhancements:**
- Dashboard UI for checkpoint approvals and execution monitoring
- PostgreSQL execution persistence (schema ready, wire to dispatcher)
- Celery-backed agent execution for background processing
- Custom pipeline builder (YAML-defined pipelines)
- Agent marketplace (community-contributed workflows)

**Full implementation plan:** `docs/plans/2026-03-22-webpilot-agent.md`

## API Approach: Option A + C (Decided)

**Option A:** Anthropic API key from `console.anthropic.com` ($5 credit, separate from subscription).
**Option C:** CSS selectors handle 90% of cases — LLM vision is the rare fallback only when selectors fail.

Combined: The agent almost never calls the API during normal execution. $5 lasts months.
Abhishek's Claude Pro subscription is for chat/Claude Code. The WebPilot agent uses its own lightweight API budget.

## Tech Stack

- Python 3.12, Playwright, browser-use, Anthropic Claude API (Sonnet 4)
- FastAPI, PostgreSQL, Redis, Celery
- Pydantic v2, SQLAlchemy 2.0, Alembic
- pytest, pytest-asyncio, ruff, mypy

## MANDATORY Build Discipline

**For EVERY task, follow this sequence:**

1. **Route through master-skill** → identify optimal skills for the task
2. **Check arsenal** → starred repos, desktop repos, /mnt/skills/user/, master-skill
3. **Follow ai-dev-standards** → 6 quality gates (Scope → Plan → Own Stack → Document → Disciplined Code → Security → Review)
4. **Domain model first** → work backwards from end goal
5. **TDD** → write tests FIRST, then implement
6. **Compound-engineering pattern** → every component logs operations; failures become lessons via `get_lessons()`
7. **Autoresearch pattern** → track success/failure rates for self-improvement loop

## Arsenal — Key Patterns to Apply

| Pattern | Source | How to Use |
|---|---|---|
| Checkpoint protocol | gsd-checkpoint-protocol skill | 3 types: human-verify (90%), decision (9%), human-action (1%) |
| Verification patterns | gsd-verification-patterns skill | Validate at load time, verify after execution |
| Error→lesson loop | EveryInc/compound-engineering-plugin | Every component has `get_lessons()` returning failed operations |
| Self-improvement loop | karpathy/autoresearch | read→modify→test→keep/revert cycle |
| Selector analytics | autoresearch pattern | Track which CSS selectors fail → improve workflows |
| Session persistence | GSD checkpoint + Playwright | Save/restore browser state for pause/resume |
| Two-tier element finding | playwright-skill + Claude vision | CSS selector first, LLM vision fallback |
| Scientific skills | K-Dense-AI/claude-scientific-skills | Finance + research agent capabilities |
| 500+ agent skills | VoltAgent/awesome-agent-skills | Mine for capability gaps |

## MANDATORY: Arsenal Patterns Deployed Table

**At the end of every sprint/milestone/deliverable**, include a table showing:

| Pattern | Source | Where Applied |
|---|---|---|
| (pattern name) | (repo/skill it came from) | (which file/component used it) |

This is non-negotiable. Abhishek uses this to understand how the project is being built.

### Sprint 3: Arsenal Patterns Deployed

| Pattern | Source | Where Applied |
|---|---|---|
| Checkpoint protocol | gsd-checkpoint-protocol skill | `src/checkpoints/manager.py` — 3 modes: CLI (human-verify), WebSocket (decision), Auto (trusted) |
| Compound-engineering | EveryInc/compound-engineering-plugin | All 3 new components: `get_lessons()`, `get_stats()` methods on CheckpointManager, RecoveryEngine, WorkflowExecutor |
| Three-tier recovery | gsd-checkpoint-protocol + recovery pattern | `src/core/recovery.py` — retry → LLM adapt → escalate to human |
| Two-tier element finding | playwright-skill + Claude vision | `src/core/recovery.py` — LLM adapt tier uses `find_element()` for new selectors |
| GSD verification | gsd-verification-patterns skill | `src/core/executor.py` — validates each step result before moving to next |
| Session persistence | GSD checkpoint + Playwright | `src/core/executor.py` — screenshots at checkpoints, state preservation |
| TDD discipline | test-driven-development skill | 64 tests written FIRST, then implementation — all green |
| ai-dev-standards | ai-dev-standards skill | Standard depth: planned → documented → tested → reviewed |

### Sprint 4: Arsenal Patterns Deployed

| Pattern | Source | Where Applied |
|---|---|---|
| Rich CLI output | Typer + Rich | `src/cli/main.py` — Tables, panels, colored output for workflows, creds, execution results |
| Dry-run pattern | GSD verification | `src/cli/main.py` + `src/api/server.py` — Preview workflow steps without launching browser |
| Factory pattern | FastAPI best practices | `src/api/server.py` — `create_app()` factory for testable API instances |
| Repository pattern | architecture-patterns skill | `src/core/database.py` — Clean async data access with SQLAlchemy |
| SQLite→PostgreSQL swap | database-architect skill | `src/core/database.py` — Zero-setup SQLite dev, one-line swap to PostgreSQL |
| Dependency injection | clean-code skill | CLI/API accept paths via options for testability (--workflows-dir, --vault-path) |
| TDD discipline | test-driven-development skill | 39 tests written FIRST, then implementation — all green |
| ai-dev-standards | ai-dev-standards skill | Standard depth: planned → documented → tested → reviewed |

### Sprint 5: Arsenal Patterns Deployed

| Pattern | Source | Where Applied |
|---|---|---|
| Structured logging | observability-engineer skill + structlog | `src/core/logging.py` — JSON/console output, context binding, SensitiveDataFilter |
| Sensitive data filtering | security hardening pattern | `src/core/logging.py` — Regex-based masking of API keys, passwords, tokens in all log output |
| Defense in depth | security hardening pattern | `src/security/middleware.py` — 4 layers: auth + rate limit + sanitize + headers |
| Strategy pattern | architecture-patterns skill | `src/tasks/queue.py` — TaskQueue protocol, swap InMemory → Celery without changing callers |
| Compound-engineering | EveryInc/compound-engineering-plugin | `src/core/logging.py` ExecutionLogger + `src/tasks/queue.py` InMemoryTaskQueue — both have `get_stats()`/`get_lessons()` |
| Input sanitization | OWASP patterns | `src/security/middleware.py` — Path traversal, XSS, injection protection on workflow names and variables |
| Mock-based testing | test-driven-development skill | `test_browser_session_mock.py` + `test_action_engine_mock.py` — Full coverage without real browser |
| TDD discipline | test-driven-development skill | 135 tests written FIRST, then implementation — all green |
| ai-dev-standards | ai-dev-standards skill | Standard depth: planned → documented → tested → reviewed |

### Phase 4: Arsenal Patterns Deployed

| Pattern | Source | Where Applied |
|---|---|---|
| Workflow library | YAML-first design | `workflows/` — 6 pre-built workflows (clerk-setup, vercel-deploy, supabase-setup, stripe-setup, github-repo, domain-setup) |
| Strategy pattern | architecture-patterns skill | `src/tasks/celery_queue.py` — CeleryTaskQueue implements same TaskQueue protocol as InMemoryTaskQueue |
| Lazy imports | Python best practices | `src/tasks/celery_queue.py` — Deferred Celery imports so module works without Celery installed |
| Compound-engineering | EveryInc/compound-engineering-plugin | `src/tasks/celery_queue.py` — `get_lessons()` tracks failure patterns |
| Database migrations | database-architect skill | `alembic/` — Async-compatible migrations for SQLite/PostgreSQL swap |
| Infrastructure as code | DevOps patterns | `docker-compose.yml` — PostgreSQL 16 + Redis 7 with health checks and persistent volumes |
| Parametrized testing | test-driven-development skill | `test_workflow_library.py` — 100 tests using pytest parametrize across all 6 workflows |
| TDD discipline | test-driven-development skill | 114 tests written FIRST, then implementation — all green |
| ai-dev-standards | ai-dev-standards skill | Standard depth: planned → documented → tested → reviewed |

### Phase 5: Arsenal Patterns Deployed

| Pattern | Source | Where Applied |
|---|---|---|
| Protocol pattern | Python Protocols (PEP 544) | `src/agents/base.py` — BaseAgent protocol with runtime_checkable, structural subtyping |
| Registry pattern | architecture-patterns skill | `src/agents/base.py` AgentRegistry — discover, register, search agents by capability/action |
| Dispatcher pattern | message-broker patterns | `src/agents/dispatcher.py` — Routes tasks to agents, stores results, tracks history |
| Adapter/Wrapper pattern | design-patterns skill | `src/agents/devops_setup.py` — Wraps WorkflowExecutor into BaseAgent protocol |
| Object pool pattern | resource-management patterns | `src/browser/session_pool.py` — Reusable browser sessions with max capacity and idle cleanup |
| Factory pattern | FastAPI best practices | `src/api/server.py` — `create_app()` wires agents, dispatcher, registry |
| Capability-based routing | multi-agent patterns | `src/agents/base.py` — AgentCapability enum, find_by_capability(), find_for_action() |
| Compound-engineering | EveryInc/compound-engineering-plugin | All new components: get_stats(), get_lessons() on Agent, Dispatcher, SessionPool |
| TDD discipline | test-driven-development skill | 54 tests written FIRST, then implementation — all green |
| ai-dev-standards | ai-dev-standards skill | Standard depth: planned → documented → tested → reviewed |

### Phase 6: Arsenal Patterns Deployed

| Pattern | Source | Where Applied |
|---|---|---|
| Multi-agent fleet | multi-agent-system pattern | `src/agents/` — 6 agents: DevOps, Research, Sales, Marketing, Finance, Manager |
| Pipeline orchestration | workflow-engine patterns | `src/agents/manager.py` — Chains agents with input mapping, conditions, global variables |
| Built-in pipelines | domain-driven design | `src/agents/manager.py` — 4 pipelines: full-saas-setup, outbound-pipeline, content-launch, revenue-health-check |
| Agent-per-domain | microservices pattern | Each agent owns its own workflow directory (`workflows/{agent}/`) |
| Input mapping | data-flow patterns | `PipelineStep.input_mapping` — pass extracted data between pipeline steps |
| Conditional execution | workflow-engine patterns | `PipelineStep.condition` — skip steps based on previous results |
| Compound-engineering | EveryInc/compound-engineering-plugin | All agents + ManagerAgent: get_stats(), get_lessons(), task logs |
| TDD discipline | test-driven-development skill | 44 tests written FIRST — all green |
| ai-dev-standards | ai-dev-standards skill | Standard depth: planned → documented → tested → reviewed |

## Code Conventions

- **Async everywhere** — all browser and DB operations use async/await
- **Pydantic for all models** — validation at the boundary
- **Structured logging** — use `from src.core.logging import get_logger; logger = get_logger(__name__)`
- **Type hints** — all functions fully typed, mypy strict mode
- **No plaintext secrets** — ever, anywhere, including logs and error messages
- **Tests next to code** — `tests/unit/`, `tests/integration/`, `tests/e2e/`

## Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific sprint
pytest tests/unit/test_vault.py -v
pytest tests/unit/test_workflow_registry.py -v
pytest tests/unit/test_browser_engine.py -v
pytest tests/unit/test_checkpoint_manager.py -v
pytest tests/unit/test_executor.py -v
pytest tests/unit/test_recovery.py -v
pytest tests/unit/test_cli.py -v
pytest tests/unit/test_api.py -v
pytest tests/unit/test_database.py -v

# Sprint 5 tests
pytest tests/unit/test_logging.py -v
pytest tests/unit/test_security.py -v
pytest tests/unit/test_task_queue.py -v
pytest tests/unit/test_config.py -v
pytest tests/unit/test_browser_session_mock.py -v
pytest tests/unit/test_action_engine_mock.py -v

# Phase 4 tests
pytest tests/unit/test_workflow_library.py -v
pytest tests/unit/test_celery_queue.py -v

# Phase 5 tests
pytest tests/unit/test_agent_system.py -v

# Phase 6 tests
pytest tests/unit/test_full_agent_fleet.py -v

# Skip integration tests (need real browser)
pytest -m "not integration"
```

## Infrastructure

```bash
# Start PostgreSQL + Redis
docker compose up -d

# Run database migrations
WEBPILOT_DATABASE_URL=postgresql+asyncpg://webpilot:webpilot@localhost:5432/webpilot alembic upgrade head

# Start Celery worker
celery -A src.tasks.celery_app worker --loglevel=info -Q workflows
```

## Project Structure

```
webpilot-agent/
├── src/
│   ├── agents/         # base.py, dispatcher.py, manager.py, devops_setup.py, research.py, sales.py, marketing.py, finance.py
│   ├── core/           # models.py, config.py, workflow_registry.py, llm_brain.py, executor.py, recovery.py, database.py, logging.py
│   ├── browser/        # session.py, actions.py, session_pool.py (BrowserSessionPool)
│   ├── checkpoints/    # manager.py
│   ├── credentials/    # vault.py
│   ├── api/            # server.py (REST + WebSocket + agent endpoints)
│   ├── cli/            # main.py
│   ├── security/       # middleware.py (API key auth, rate limiting, input sanitization, security headers)
│   └── tasks/          # queue.py, celery_app.py, celery_queue.py, worker.py
├── workflows/          # 26 YAML workflows organized by agent
│   ├── *.yaml          # DevOps: clerk-setup, vercel-deploy, supabase-setup, stripe-setup, github-repo, domain-setup
│   ├── research/       # competitor-analysis, lead-research, market-validation, tech-stack-detect, content-research
│   ├── sales/          # linkedin-connect, crm-entry, email-campaign, meeting-setup, proposal-gen
│   ├── marketing/      # social-post, seo-audit, blog-outline, newsletter-setup, analytics-report
│   └── finance/        # invoice-tracker, payment-monitor, expense-report, subscription-audit, revenue-dashboard
├── alembic/            # Database migrations (async-compatible)
├── tests/              # 490+ tests passing
├── docs/plans/         # Implementation plan
├── docker-compose.yml  # PostgreSQL 16 + Redis 7
└── CLAUDE.md           # THIS FILE
```
