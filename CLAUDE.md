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

**Total: 7/17 tasks complete, 105 tests passing**

## What to Build Next

**Sprint 3: Orchestration (3 tasks)**
- Task 8: Checkpoint system (`src/checkpoints/manager.py`) — CLI + WebSocket + auto-approve modes
- Task 9: Workflow executor (`src/core/executor.py`) — The central loop that runs workflows step-by-step
- Task 10: Recovery engine (`src/core/recovery.py`) — Three-tier: retry → LLM adapt → escalate to checkpoint

**Sprint 4: Interfaces (3 tasks)**
- Task 11: CLI (`src/cli/main.py`) — Typer CLI: `webpilot run`, `webpilot list`, `webpilot creds`
- Task 12: FastAPI server + WebSocket checkpoints (`src/api/`)
- Task 13: Database layer (`src/core/database.py`, `src/core/db_models.py`, alembic/)

**Sprint 5: Production Hardening (4 tasks)**
- Task 14: Celery + Redis async queue
- Task 15: Structured logging (structlog)
- Task 16: Security hardening
- Task 17: Full test coverage (80%+ target)

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

## Code Conventions

- **Async everywhere** — all browser and DB operations use async/await
- **Pydantic for all models** — validation at the boundary
- **Structured logging** — use `logging.getLogger(__name__)`
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

# Skip integration tests (need real browser)
pytest -m "not integration"
```

## Project Structure

```
webpilot-agent/
├── src/
│   ├── core/           # models.py, config.py, workflow_registry.py, llm_brain.py, executor.py (TODO)
│   ├── browser/        # session.py, actions.py
│   ├── checkpoints/    # manager.py (TODO)
│   ├── credentials/    # vault.py
│   ├── api/            # server.py, routes/ (TODO)
│   └── cli/            # main.py (TODO)
├── workflows/          # clerk-setup.yaml + future workflows
├── tests/              # 105 tests passing
├── docs/plans/         # Implementation plan
└── CLAUDE.md           # THIS FILE
```
