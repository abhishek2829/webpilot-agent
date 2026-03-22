# WebPilot Agent — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a semi-autonomous browser agent that executes multi-step web workflows (SaaS setup, data extraction, form filling) with human-in-the-loop checkpoints — designed for personal use AND productization as a paid service.

**Architecture:** Python-based orchestrator that decomposes natural language goals into YAML-defined workflows, executes them via Playwright browser sessions guided by Claude's vision + reasoning, and pauses at configurable checkpoints for human approval. FastAPI serves the productization API layer.

**Tech Stack:** Python 3.12, browser-use, Playwright, Anthropic Claude API (Sonnet 4), FastAPI, PostgreSQL, Redis, WebSockets, Pydantic v2, SQLAlchemy 2.0, Alembic, pytest

---

## Phase 0: Scope Assessment (ai-dev-standards)

| Dimension | Assessment |
|---|---|
| **Intent clarity** | Clear — semi-autonomous browser agent with checkpoint system |
| **Codebase state** | Greenfield — new project from scratch |
| **Complexity** | High — multi-system (browser, LLM, queue, DB, API) |
| **Risk** | Medium-high — credential handling, real browser actions |

**Depth Level: STANDARD** — All 6 phases at standard depth. Architecture documented, dependencies justified, tests written, security checked.

---

## Phase 1: Plan Before You Build

### 1.1 Problem Statement

**What:** A Python agent that navigates websites and performs multi-step tasks autonomously, with human approval at critical moments.

**Who:** Abhishek (personal automation) → eventually external clients via API.

**Why:** Setting up Clerk, Vercel, Supabase, Stripe etc. for each new project takes 30-60 min of repetitive clicking. This agent reduces it to a single command + 2-3 checkpoint approvals.

**Success Criteria:**
- [ ] Can execute the Clerk setup workflow end-to-end with ≤3 checkpoints
- [ ] Handles website changes gracefully via LLM vision fallback
- [ ] Checkpoint system pauses and resumes reliably
- [ ] API layer serves workflows to external clients
- [ ] All credentials encrypted at rest, never logged in plaintext
- [ ] Average workflow execution < 3 minutes for simple 5-step flows

### 1.2 Domain Model

```
Goal (NL text)
  └── decomposed into → Workflow (YAML recipe)
       └── contains → Step[] (ordered browser actions)
            ├── NavigateStep (go to URL)
            ├── ClickStep (click element by selector/vision)
            ├── TypeStep (fill input field)
            ├── ExtractStep (copy text/value from page)
            ├── WaitStep (wait for condition)
            └── CheckpointStep (pause for human approval)

WorkflowExecution (runtime instance)
  ├── has → BrowserSession (Playwright context)
  ├── produces → ExecutionLog[] (step results, screenshots)
  ├── uses → CredentialVault (encrypted secrets)
  └── managed by → LLMBrain (Claude API — vision + reasoning)
```

### 1.3 Architecture — Layer Breakdown

```
┌─────────────────────────────────────────────────┐
│  Layer 0: Interface (CLI + FastAPI + WebSocket)  │
├─────────────────────────────────────────────────┤
│  Layer 1: Orchestrator (Goal → Workflow → Steps) │
├─────────────────────────────────────────────────┤
│  Layer 2: Browser Agent (Playwright + Vision)    │
├─────────────────────────────────────────────────┤
│  Layer 3: Intelligence (Claude API)              │
├─────────────────────────────────────────────────┤
│  Layer 4: Storage (PostgreSQL + Redis + Vault)   │
└─────────────────────────────────────────────────┘
```

### 1.4 Tech Stack Rationale

| Component | Choice | Why (not AI-defaulted) |
|---|---|---|
| Language | Python 3.12 | browser-use is Python-native, best LLM SDK support, Abhishek's strength |
| Browser engine | browser-use + Playwright | Open source, production-grade, combines DOM + vision + action in one lib |
| LLM | Claude Sonnet 4 (via Anthropic SDK) | Best vision model for screenshots, strong reasoning, native tool use |
| API framework | FastAPI | Async-native, auto OpenAPI docs, WebSocket support built-in |
| Database | PostgreSQL 16 | Workflows, execution logs, user data — battle-tested |
| Queue/Cache | Redis 7 | Session state, task queue (via Celery), real-time checkpoint pub/sub |
| ORM | SQLAlchemy 2.0 + Alembic | Type-safe, async support, reliable migrations |
| Validation | Pydantic v2 | Workflow YAML → typed models, API request/response validation |
| Credential mgmt | cryptography (Fernet) | Encrypt secrets at rest, no external vault dependency for MVP |
| Testing | pytest + pytest-asyncio + playwright fixtures | Full coverage: unit, integration, e2e browser tests |

**Rejected alternatives:**
- Selenium → slower, no modern async, Playwright is strictly better
- LangChain → unnecessary abstraction layer for direct Claude API calls
- Stagehand → newer, less community, browser-use is more mature
- Anthropic Computer Use (beta) → full desktop control is overkill; browser-only is scoped better
- Node.js/Puppeteer → weaker LLM SDK ecosystem, Abhishek's Python is stronger

---

## Phase 2: Own Your Stack — Dependency Matrix

| Package | Version | Purpose | Fallback |
|---|---|---|---|
| browser-use | ≥0.2.x | Browser automation + LLM integration | Raw Playwright + custom LLM loop |
| playwright | ≥1.45 | Browser control | — (core, no fallback) |
| anthropic | ≥0.40 | Claude API SDK | Direct HTTP calls |
| fastapi | ≥0.115 | API layer | Flask (less ideal) |
| uvicorn | ≥0.30 | ASGI server | hypercorn |
| sqlalchemy | ≥2.0 | ORM + async queries | asyncpg raw |
| alembic | ≥1.13 | DB migrations | — |
| redis | ≥5.0 (py-redis) | Cache + pub/sub | In-memory dict (dev only) |
| celery | ≥5.4 | Task queue | arq (lighter) |
| pydantic | ≥2.9 | Validation | dataclasses + manual |
| cryptography | ≥43.0 | Fernet encryption | — |
| pyyaml | ≥6.0 | Workflow YAML parsing | — |
| websockets | ≥13.0 | Real-time checkpoints | SSE fallback |
| rich | ≥13.0 | CLI output | click |
| typer | ≥0.12 | CLI framework | argparse |

**POC to validate before full build:**
1. browser-use can navigate Clerk.com and click "Create Application"
2. Claude vision API can read a Clerk dashboard screenshot and extract API keys
3. WebSocket checkpoint flow works (send screenshot → wait for approval → resume)

---

## Phase 3: Task Breakdown

### Sprint 1: Foundation (Week 1) — "Walk before you run"

#### Task 1: Project Bootstrap + Config
**Files:**
- Create: `pyproject.toml`
- Create: `src/__init__.py`
- Create: `src/core/__init__.py`
- Create: `src/core/config.py`
- Create: `src/core/models.py`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `README.md`

**Done criteria:** `pip install -e .` succeeds, `python -c "from src.core.config import settings"` works

---

#### Task 2: Domain Models (Pydantic)
**Files:**
- Create: `src/core/models.py`
- Test: `tests/unit/test_models.py`

**Step 1: Write failing tests**
```python
# tests/unit/test_models.py
from src.core.models import Workflow, Step, StepType, CheckpointConfig

def test_workflow_from_yaml():
    yaml_str = """
    name: clerk-setup
    description: Set up Clerk authentication
    steps:
      - type: navigate
        url: https://clerk.com
      - type: click
        selector: "[data-testid='create-app']"
      - type: checkpoint
        message: "Confirm app creation?"
        screenshot: true
    """
    wf = Workflow.from_yaml(yaml_str)
    assert wf.name == "clerk-setup"
    assert len(wf.steps) == 3
    assert wf.steps[2].type == StepType.CHECKPOINT

def test_step_validation_rejects_empty_url():
    with pytest.raises(ValidationError):
        Step(type=StepType.NAVIGATE, url="")
```

**Step 2: Implement models**
```python
# src/core/models.py — key models
class StepType(str, Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    EXTRACT = "extract"
    WAIT = "wait"
    CHECKPOINT = "checkpoint"

class Step(BaseModel):
    type: StepType
    url: str | None = None
    selector: str | None = None
    text: str | None = None
    variable: str | None = None       # store extracted value
    message: str | None = None         # checkpoint message
    screenshot: bool = False
    timeout_seconds: int = 30
    fallback_strategy: str = "llm_vision"  # what to do if selector fails

class Workflow(BaseModel):
    name: str
    description: str
    version: str = "1.0"
    steps: list[Step]
    variables: dict[str, str] = {}     # runtime variables (e.g., project name)
    credentials_required: list[str] = []  # e.g., ["clerk_email", "clerk_password"]
```

**Done criteria:** `pytest tests/unit/test_models.py -v` — all pass

---

#### Task 3: Credential Vault
**Files:**
- Create: `src/credentials/vault.py`
- Create: `src/credentials/__init__.py`
- Test: `tests/unit/test_vault.py`

**Step 1: Failing test**
```python
def test_store_and_retrieve_credential():
    vault = CredentialVault(encryption_key="test-key-32-chars-long-exactly!!")
    vault.store("clerk_email", "test@example.com")
    assert vault.retrieve("clerk_email") == "test@example.com"

def test_credential_encrypted_at_rest(tmp_path):
    vault = CredentialVault(encryption_key="test-key-32-chars-long-exactly!!", storage_path=tmp_path / "creds.enc")
    vault.store("api_key", "sk_live_secret123")
    raw_content = (tmp_path / "creds.enc").read_bytes()
    assert b"sk_live_secret123" not in raw_content  # must be encrypted
```

**Step 2: Implement Fernet-based vault**

**Done criteria:** Tests pass, credentials never stored in plaintext

---

#### Task 4: Workflow YAML Parser + Registry
**Files:**
- Create: `src/core/workflow_registry.py`
- Create: `workflows/clerk-setup.yaml`
- Test: `tests/unit/test_workflow_registry.py`

**Step 1: Create first workflow YAML**
```yaml
# workflows/clerk-setup.yaml
name: clerk-setup
description: Set up Clerk authentication for a new project
version: "1.0"
variables:
  project_name: ""        # required — user provides
  auth_methods: "google,email"  # default
credentials_required:
  - clerk_email
  - clerk_password

steps:
  - type: navigate
    url: https://clerk.com/dashboard
    
  - type: checkpoint
    message: "Ready to create Clerk app '{{project_name}}'?"
    screenshot: true

  - type: click
    selector: "button:has-text('Add application')"
    fallback_strategy: llm_vision
    
  - type: type
    selector: "input[name='name']"
    text: "{{project_name}}"
    
  - type: click
    selector: "[data-testid='google-provider']"
    
  - type: click
    selector: "[data-testid='email-provider']"
    
  - type: click
    selector: "button:has-text('Create application')"
    
  - type: checkpoint
    message: "Application created. Confirm to extract API keys?"
    screenshot: true
    
  - type: extract
    selector: ".cl-publishable-key"
    variable: "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"
    fallback_strategy: llm_vision
    
  - type: extract
    selector: ".cl-secret-key"
    variable: "CLERK_SECRET_KEY"
    fallback_strategy: llm_vision
```

**Done criteria:** Registry loads YAML, resolves `{{variables}}`, returns typed Workflow

---

### Sprint 2: Browser Engine (Week 2) — "Teach it to see and act"

#### Task 5: Browser Session Manager
**Files:**
- Create: `src/browser/session.py`
- Create: `src/browser/__init__.py`
- Test: `tests/integration/test_browser_session.py`

**Core responsibilities:**
- Launch Playwright browser (headed for debug, headless for prod)
- Manage browser context (cookies, storage state for logged-in sessions)
- Take screenshots at each step
- Persist session state between runs (stay logged in)

**Done criteria:** Can launch browser, navigate to a URL, take screenshot, close cleanly

---

#### Task 6: Action Engine (Click, Type, Extract, Wait)
**Files:**
- Create: `src/browser/actions.py`
- Test: `tests/integration/test_actions.py`

**Core pattern — two-tier element finding:**
```python
async def find_element(page, step: Step) -> ElementHandle | None:
    # Tier 1: Try CSS/XPath selector (fast, deterministic)
    if step.selector:
        try:
            element = await page.wait_for_selector(step.selector, timeout=5000)
            if element:
                return element
        except TimeoutError:
            pass
    
    # Tier 2: Fall back to LLM vision (adaptive, slower)
    if step.fallback_strategy == "llm_vision":
        screenshot = await page.screenshot()
        element_description = await llm_find_element(screenshot, step)
        return await page.locator(element_description).first
    
    raise ElementNotFoundError(f"Could not find element for step: {step}")
```

**Done criteria:** All 5 action types work against a local test HTML page

---

#### Task 7: LLM Vision Integration
**Files:**
- Create: `src/core/llm_brain.py`
- Test: `tests/unit/test_llm_brain.py`

**Two LLM functions:**
1. `llm_find_element(screenshot, step)` → Returns selector/coordinates when CSS fails
2. `llm_extract_value(screenshot, description)` → Reads text from screenshot when DOM extraction fails

```python
async def llm_find_element(screenshot_bytes: bytes, step: Step) -> str:
    """Ask Claude to find an element on the page via vision."""
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", 
                 "data": base64.b64encode(screenshot_bytes).decode()}},
                {"type": "text", "text": f"Find the element matching: {step.description or step.selector}. "
                 "Return ONLY a CSS selector or aria-label that uniquely identifies it."}
            ]
        }]
    )
    return response.content[0].text.strip()
```

**Done criteria:** Vision correctly identifies "Create Application" button on a Clerk screenshot

---

### Sprint 3: Orchestration (Week 3) — "The brain that connects everything"

#### Task 8: Checkpoint System
**Files:**
- Create: `src/checkpoints/manager.py`
- Create: `src/checkpoints/__init__.py`
- Test: `tests/unit/test_checkpoint_manager.py`

**Three checkpoint modes:**
1. **CLI mode** — prints screenshot path + message, waits for y/n input
2. **WebSocket mode** — pushes to connected dashboard, waits for approval event
3. **Auto-approve mode** — for trusted workflows in production (configurable per-step)

```python
class CheckpointManager:
    async def request_approval(self, step: Step, screenshot: bytes, context: dict) -> CheckpointResult:
        """Pause execution and wait for human approval."""
        # Emit checkpoint event
        checkpoint = CheckpointEvent(
            step_index=context["step_index"],
            message=step.message,
            screenshot_b64=base64.b64encode(screenshot).decode(),
            variables=context.get("variables", {}),
            timestamp=datetime.utcnow()
        )
        
        # Wait for response based on mode
        if self.mode == "cli":
            return await self._cli_approval(checkpoint)
        elif self.mode == "websocket":
            return await self._ws_approval(checkpoint)
        elif self.mode == "auto":
            return CheckpointResult(approved=True, by="auto")
```

**Done criteria:** CLI checkpoint pauses, shows info, resumes on 'y', aborts on 'n'

---

#### Task 9: Workflow Executor (The Orchestrator)
**Files:**
- Create: `src/core/executor.py`
- Test: `tests/integration/test_executor.py`

**This is the central loop — the heartbeat of the agent:**
```python
class WorkflowExecutor:
    async def execute(self, workflow: Workflow, variables: dict) -> ExecutionResult:
        """Execute a workflow step by step."""
        session = await self.browser_manager.create_session()
        execution_log = []
        
        for i, step in enumerate(workflow.resolved_steps(variables)):
            try:
                if step.type == StepType.CHECKPOINT:
                    screenshot = await session.screenshot()
                    result = await self.checkpoint_mgr.request_approval(step, screenshot, {"step_index": i, "variables": variables})
                    if not result.approved:
                        return ExecutionResult(status="aborted", step=i, reason=result.reason)
                else:
                    result = await self.action_engine.execute(session, step)
                    
                execution_log.append(StepResult(step=i, status="success", data=result))
                
            except Exception as e:
                # Recovery: retry once, then ask LLM for help, then checkpoint
                recovery = await self.recovery_engine.handle(session, step, e)
                if not recovery.resolved:
                    return ExecutionResult(status="failed", step=i, error=str(e))
        
        return ExecutionResult(status="completed", log=execution_log, extracted=variables)
```

**Done criteria:** Executor runs the clerk-setup.yaml workflow with mock browser, hits checkpoints, completes

---

#### Task 10: Recovery Engine
**Files:**
- Create: `src/core/recovery.py`
- Test: `tests/unit/test_recovery.py`

**Three-tier recovery strategy:**
1. **Retry** — same action, fresh page state (handles transient failures)
2. **LLM Adapt** — screenshot the current page, ask Claude "the selector failed, find the element"
3. **Escalate to Checkpoint** — show user the failure + screenshot, ask how to proceed

**Done criteria:** Recovery handles selector-not-found, page-timeout, unexpected-dialog

---

### Sprint 4: Interface Layer (Week 4) — "Make it usable"

#### Task 11: CLI Interface
**Files:**
- Create: `src/cli/main.py`
- Create: `src/cli/__init__.py`

**Commands:**
```bash
# Run a workflow
webpilot run clerk-setup --var project_name=MyApp

# List available workflows  
webpilot list

# Store credentials
webpilot creds set clerk_email user@example.com
webpilot creds set clerk_password --secret  # prompts for hidden input

# View execution history
webpilot history

# Resume a paused execution
webpilot resume <execution_id>
```

**Done criteria:** `webpilot run clerk-setup --var project_name=TestApp` executes full workflow

---

#### Task 12: FastAPI Server + WebSocket Checkpoints
**Files:**
- Create: `src/api/server.py`
- Create: `src/api/routes/workflows.py`
- Create: `src/api/routes/checkpoints.py`
- Create: `src/api/routes/executions.py`
- Create: `src/api/__init__.py`

**Key endpoints:**
```
POST   /api/v1/workflows/execute    — Start a workflow execution
GET    /api/v1/workflows             — List available workflows
GET    /api/v1/executions/{id}       — Get execution status + logs
POST   /api/v1/checkpoints/{id}/approve  — Approve a checkpoint
POST   /api/v1/checkpoints/{id}/reject   — Reject a checkpoint
WS     /ws/executions/{id}           — Real-time execution stream
```

**Done criteria:** API starts, Swagger docs at /docs, can trigger workflow via HTTP

---

#### Task 13: Database Layer (PostgreSQL + SQLAlchemy)
**Files:**
- Create: `src/core/database.py`
- Create: `src/core/db_models.py`
- Create: `alembic/` (via `alembic init`)
- Create: `alembic/versions/001_initial.py`

**Tables:**
- `workflows` — name, yaml_content, version, created_at
- `executions` — workflow_id, status, variables, started_at, completed_at
- `execution_steps` — execution_id, step_index, status, screenshot_path, result_data
- `checkpoints` — execution_id, step_index, status, approved_by, responded_at
- `credentials` — key, encrypted_value, created_at, updated_at

**Done criteria:** Migrations run, execution history persists across restarts

---

### Sprint 5: Production Hardening (Week 5) — "Make it reliable"

#### Task 14: Async Task Queue (Celery + Redis)
- Long-running workflows execute in background workers
- WebSocket pushes real-time updates to connected clients
- Execution survives server restart (persisted state in Redis)

#### Task 15: Logging + Observability
- Structured JSON logging (structlog)
- Screenshot archive per execution (S3 or local)
- Execution metrics (duration, success rate, common failures)

#### Task 16: Security Hardening
- API key authentication for external clients
- Rate limiting (slowapi)
- Credential vault encryption key from environment variable
- No plaintext secrets in logs, DB, or screenshots
- Input sanitization on all API endpoints

#### Task 17: Tests — Full Coverage
- Unit tests: models, vault, recovery, LLM prompts
- Integration tests: browser actions against local test server
- E2E tests: full Clerk workflow against staging
- Target: 80%+ coverage

---

## Phase 4: Workflow Library (Post-MVP)

Pre-built YAML workflows to ship with the agent:

| Workflow | Steps | Checkpoints |
|---|---|---|
| `clerk-setup` | Navigate → Create App → Configure Auth → Extract Keys | Before create, before extract |
| `vercel-deploy` | Navigate → Import Repo → Configure → Deploy | Before deploy |
| `supabase-setup` | Navigate → Create Project → Copy Keys → Create Tables | Before create, before schema |
| `stripe-setup` | Navigate → Create Account → Configure Webhooks → Extract Keys | Before each action |
| `github-repo` | Navigate → Create Repo → Configure Settings → Add Secrets | Before create |
| `domain-setup` | Navigate → Purchase/Configure → Set DNS → Verify | Before purchase |

---

## Phase 5: Multi-Agent System Integration

This agent becomes `DevOpsSetupAgent` in the Multi-Agent System:

```
Manager Agent
├── DevOpsSetupAgent (THIS PROJECT — WebPilot)
│   ├── clerk-setup workflow
│   ├── vercel-deploy workflow
│   └── supabase-setup workflow
├── ResearchAgent (future — uses same browser layer)
├── SalesAgent (future — LinkedIn automation)
├── MarketingAgent (future — social media)
└── FinanceAgent (future — invoice/payment tracking)
```

**Shared infrastructure:** Browser session pool, credential vault, checkpoint system, execution logs — all reusable across agents.

---

## Quality Gates Checklist (ai-dev-standards)

| # | Phase | Gate | Status |
|---|---|---|---|
| 0 | Scope | Depth level = Standard ✓ | ⬜ |
| 1 | Plan | Problem statement + architecture + task breakdown | ⬜ |
| 2 | Stack | Every dependency justified + POC validates | ⬜ |
| 3 | Docs | Decision log + architecture diagram + README | ⬜ |
| 4 | Code | Feature branches + meaningful commits + CI + 80% tests | ⬜ |
| 5 | Security | Encrypted creds + no secrets in logs + input validation | ⬜ |
| 6 | Review | Every file read + business logic verified + edge cases | ⬜ |
