# WebPilot Agent

**AI browser agents that automate the web tasks you hate.**

7 specialized agents. 33 workflows. 8 multi-agent pipelines. Human approval at every critical step.

---

## What It Does

WebPilot opens a real browser, navigates websites, clicks buttons, fills forms, and extracts data — with human checkpoints before anything irreversible. When a website changes its UI, Claude's vision API adapts automatically.

```bash
# Set up your entire SaaS stack in 10 minutes
webpilot run full-saas-setup --var project_name=MyApp

# Research 10 competitors automatically
webpilot run competitor-analysis --var competitor_url=https://competitor.com

# Full outbound pipeline: research -> LinkedIn -> CRM
POST /api/pipelines/outbound-pipeline/run
{"parameters": {"company_url": "https://target.com"}}
```

## 7 Agents

| Agent | What It Automates | Workflows |
|-------|-------------------|-----------|
| **DevOps Setup** | Clerk, Vercel, Supabase, Stripe, GitHub, domains | 6 |
| **Research** | Competitor analysis, lead research, market validation, tech stacks, SEO | 5 |
| **Sales** | LinkedIn outreach, CRM entry, email campaigns, meetings, proposals | 5 |
| **Marketing** | Social posting, SEO audits, blog outlines, newsletters, analytics | 5 |
| **Finance** | Invoices, payments, expenses, subscriptions, revenue dashboards | 5 |
| **Growth** | Lead generation, qualification, outreach campaigns, pipeline tracking | 7 |
| **Manager** | Chains agents into multi-step pipelines with data flow between steps | 8 pipelines |

## Multi-Agent Pipelines

Chain agents together for complex workflows:

| Pipeline | What Happens |
|----------|-------------|
| `full-saas-setup` | GitHub -> Clerk -> Supabase -> Stripe -> Vercel |
| `outbound-pipeline` | Research company -> Find CTO -> LinkedIn connect -> CRM entry |
| `content-launch` | Research topic -> Blog outline -> Newsletter -> Social post |
| `revenue-health-check` | Revenue dashboard -> Invoices -> Payments -> Subscriptions |
| `lead-gen-pipeline` | Find hot leads -> Qualify -> Track pipeline |
| `nurture-convert-pipeline` | LinkedIn outreach -> Email follow-up -> Track |
| `content-distribute-pipeline` | Post to Twitter -> LinkedIn -> Track engagement |
| `weekly-growth-cycle` | Find -> Qualify -> Outreach -> Content -> Track |

## Quick Start

```bash
# Clone and install
git clone https://github.com/YOUR_USERNAME/webpilot-agent.git
cd webpilot-agent
pip install -e ".[dev]"
playwright install chromium

# Configure
cp .env.example .env
# Add your Anthropic API key ($5 credit from console.anthropic.com)
# Generate vault key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Store credentials
webpilot creds set clerk_email your@email.com
webpilot creds set clerk_password --secret

# See available workflows
webpilot list

# Dry run (preview steps without opening browser)
webpilot run clerk-setup --var project_name=TestApp --dry-run

# Real run
webpilot run clerk-setup --var project_name=TestApp
```

## How It Works

```
User (CLI / API / Dashboard)
        |
   Agent Dispatcher (routes to the right agent)
        |
   Specialized Agent (DevOps / Research / Sales / ...)
        |
   Workflow Executor (reads YAML, runs steps)
        |
   Browser Engine (Playwright + Claude Vision)
        |
   Target Website (any web interface)
```

**Two-tier element finding:**
1. CSS selectors (fast, deterministic) -- handles 90% of cases
2. Claude vision API fallback (adaptive) -- takes a screenshot, asks Claude "where's the button?"

**Human checkpoints:** Before creating accounts, sending messages, or deploying code, the agent pauses and shows you a screenshot. You approve or reject.

## Workflow Format

Workflows are simple YAML files:

```yaml
name: clerk-setup
description: Set up Clerk authentication
variables:
  project_name: ""
credentials_required:
  - clerk_email
  - clerk_password
steps:
  - type: navigate
    url: https://dashboard.clerk.com
  - type: checkpoint
    message: "Ready to create app '{{project_name}}'?"
    screenshot: true
  - type: click
    selector: "button:has-text('Add application')"
    fallback_strategy: llm_vision
  - type: extract
    selector: "code:has-text('pk_')"
    variable: NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
```

Add your own workflows in `workflows/` — no Python code needed.

## API Server

```bash
# Start infrastructure
docker compose up -d  # PostgreSQL + Redis

# Start the API
uvicorn src.api.server:create_app --factory --reload

# Swagger docs at http://localhost:8000/docs
```

**Key endpoints:**
```
GET  /api/agents                    List all agents
GET  /api/workflows                 List all workflows
POST /api/executions                Start a workflow execution
GET  /api/executions/{id}           Check execution status
GET  /api/pipelines                 List available pipelines
POST /api/pipelines/{name}/run      Run a multi-agent pipeline
GET  /api/stats                     System-wide statistics
WS   /ws/checkpoints/{id}           Real-time checkpoint approvals
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12 |
| Browser | Playwright |
| AI | Claude Sonnet 4 (vision + reasoning) |
| API | FastAPI + WebSocket |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 async |
| Queue | Celery + Redis 7 |
| Validation | Pydantic v2 |
| Security | Fernet encryption, API key auth, rate limiting |
| Testing | pytest, 524+ tests |

## Project Structure

```
webpilot-agent/
├── src/
│   ├── agents/         # 7 agents: devops, research, sales, marketing, finance, growth, manager
│   ├── core/           # Models, config, executor, LLM brain, recovery, database
│   ├── browser/        # Playwright session, actions, session pool
│   ├── checkpoints/    # Human approval (CLI, WebSocket, auto modes)
│   ├── credentials/    # Encrypted vault (Fernet)
│   ├── api/            # FastAPI REST + WebSocket server
│   ├── cli/            # Typer CLI
│   ├── security/       # Auth, rate limiting, input sanitization
│   └── tasks/          # Celery workers, task queue
├── workflows/          # 33 YAML workflows organized by agent
│   ├── *.yaml          # DevOps workflows
│   ├── research/       # Research workflows
│   ├── sales/          # Sales workflows
│   ├── marketing/      # Marketing workflows
│   ├── finance/        # Finance workflows
│   └── growth/         # Growth workflows
├── marketing/          # Launch content, outreach templates, landing page copy
├── alembic/            # Database migrations
├── docker-compose.yml  # PostgreSQL + Redis
└── tests/              # 524+ tests
```

## Development

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific agent tests
pytest tests/unit/test_agent_system.py -v
pytest tests/unit/test_full_agent_fleet.py -v
pytest tests/unit/test_growth_agent.py -v
```

## Contributing

PRs welcome. Add new workflows, agents, or improve existing ones.

1. Fork the repo
2. Create a branch (`git checkout -b feature/my-workflow`)
3. Add your workflow YAML + tests
4. Submit a PR

## License

MIT

---

**Stop clicking. Start shipping.**
