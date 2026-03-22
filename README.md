# WebPilot Agent

> Semi-autonomous browser agent for web workflow automation with human-in-the-loop checkpoints.

WebPilot executes multi-step web workflows — setting up SaaS tools, configuring services, extracting data — while pausing at critical moments for your approval. Think of it as a self-driving car for the web that asks before making turns at dangerous intersections.

## What it does

```bash
# Set up Clerk auth for a new project — in one command
webpilot run clerk-setup --var project_name=MyApp

# Agent navigates to Clerk → creates app → configures Google + Email auth
# → pauses for your approval → extracts API keys → returns them
```

## Architecture

```
User (CLI/API/Dashboard)
        ↓
Orchestrator (Goal → Workflow → Steps)
        ↓
Browser Agent (Playwright + Claude Vision)
        ↓
Target Websites (Clerk, Vercel, Supabase, Stripe...)
```

**Key design decisions:**
- **YAML workflows** — Reusable, versionable, shareable recipes
- **Two-tier element finding** — CSS selector first (fast), LLM vision fallback (adaptive)
- **Human checkpoints** — Agent pauses before destructive/sensitive actions
- **Encrypted credentials** — Fernet encryption, never logged in plaintext

## Tech Stack

| Component | Technology | Why |
|---|---|---|
| Language | Python 3.12 | browser-use native, best LLM SDK support |
| Browser | Playwright via browser-use | DOM + Vision + Actions in one lib |
| LLM | Claude Sonnet 4 | Best vision model for screenshots |
| API | FastAPI + WebSocket | Async-native, real-time checkpoints |
| Database | PostgreSQL + Redis | Workflows, logs, sessions, queue |
| Security | Fernet encryption | Credentials encrypted at rest |

## Quick Start

```bash
# Clone
git clone <repo-url>
cd webpilot-agent

# Install
pip install -e ".[dev]"
playwright install chromium

# Configure
cp .env.example .env
# Edit .env with your Anthropic API key and vault encryption key

# Store credentials for Clerk
webpilot creds set clerk_email your@email.com
webpilot creds set clerk_password --secret

# Run a workflow
webpilot run clerk-setup --var project_name=MyNewApp
```

## Workflow Format

Workflows are YAML files in the `workflows/` directory:

```yaml
name: my-workflow
description: What this workflow does
variables:
  project_name: ""
credentials_required:
  - my_email
steps:
  - type: navigate
    url: https://example.com
  - type: checkpoint
    message: "Ready to proceed?"
    screenshot: true
  - type: click
    selector: "button.submit"
    fallback_strategy: llm_vision
  - type: extract
    variable: API_KEY
```

## Available Workflows

| Workflow | Description | Checkpoints |
|---|---|---|
| `clerk-setup` | Set up Clerk authentication | 2 |
| `vercel-deploy` | Deploy to Vercel (coming soon) | 2 |
| `supabase-setup` | Create Supabase project (coming soon) | 3 |
| `stripe-setup` | Configure Stripe (coming soon) | 3 |

## Project Structure

```
webpilot-agent/
├── src/
│   ├── core/           # Domain models, config, executor, LLM brain
│   ├── browser/        # Playwright session, actions, vision
│   ├── checkpoints/    # Human approval system (CLI, WebSocket)
│   ├── credentials/    # Encrypted credential vault
│   ├── api/            # FastAPI server + routes
│   └── cli/            # Typer CLI commands
├── workflows/          # YAML workflow definitions
├── tests/              # Unit, integration, e2e tests
├── docs/plans/         # Implementation plans
└── data/screenshots/   # Execution screenshots (gitignored)
```

## Development

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Lint + format
ruff check . --fix
ruff format .

# Type check
mypy src/
```

## License

MIT
