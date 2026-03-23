# Reddit Posts — Ready to Post

---

## r/SideProject

**Title:** I built an open-source AI agent platform that automates repetitive browser tasks

**Body:**
Hey r/SideProject,

I've been working on WebPilot Agent for the past 6 months. It's an open-source Python platform with 6 AI agents that automate browser-based tasks.

**What it does:**
- DevOps Agent: sets up Clerk + Supabase + Vercel + Stripe in one command
- Research Agent: automated competitor analysis and lead research
- Sales Agent: LinkedIn outreach + CRM data entry
- Marketing Agent: SEO audits, social posting, analytics extraction
- Finance Agent: invoice tracking, revenue dashboards
- Manager Agent: chains agents into multi-step pipelines

**How it works:**
Workflows are YAML files. The agent uses Playwright to control a real browser. When a CSS selector fails, Claude's vision API looks at a screenshot and finds the element. Human checkpoints pause before any critical action.

**Tech:** Python, Playwright, Claude API, FastAPI, PostgreSQL, Redis. 490+ tests.

Looking for feedback. What workflows would you find useful?

GitHub: [LINK]

---

## r/SaaS

**Title:** I automated my entire SaaS project setup — GitHub, auth, database, payments, deploy in 10 minutes

**Body:**
Every time I start a new SaaS project, I spend 2 hours clicking through dashboards:

- Clerk: create app, configure auth, copy API keys
- Supabase: create project, wait, copy 3 API keys
- Stripe: find keys, set up webhooks
- Vercel: import repo, deploy
- GitHub: create repo, add secrets

I built WebPilot Agent to automate all of this. One command, 10 minutes, all API keys extracted:

```
webpilot run full-saas-setup --var project_name=MyApp
```

It opens a real browser, navigates each dashboard, and does the clicking for you. It pauses at checkpoints for your approval — you review a screenshot and say yes or no.

The key: when websites change their UI, the agent uses Claude's vision API to find elements on the page instead of failing. No more broken Selenium scripts.

It's open source (Python + Playwright). 26 workflows, 6 agents.

Anyone else solving this problem differently? Would love to hear what your setup process looks like.

---

## r/startups

**Title:** We reduced developer onboarding from a full day to 15 minutes using AI browser agents

**Body:**
One of the biggest time sinks at growing startups: onboarding new engineers.

Day 1 typically involves: create GitHub access, set up Clerk account, provision Supabase project, configure Stripe test mode, deploy to Vercel staging, set up local environment variables.

That's a full day of clicking through dashboards and copying API keys.

We built WebPilot Agent to automate this. It's an open-source platform that:

1. Opens a real browser (Playwright)
2. Navigates each SaaS dashboard
3. Creates accounts, configures settings, extracts API keys
4. Pauses at checkpoints for human approval
5. Outputs all environment variables at the end

The "full-saas-setup" pipeline chains 5 tools together. New engineer gets all their keys in 15 minutes.

For DevOps teams dealing with this: what does your onboarding process look like today? How long does it take?

Open source: [LINK]

---

## r/Python

**Title:** I built a multi-agent browser automation platform in Python — Playwright + Claude Vision + FastAPI

**Body:**
I just open-sourced WebPilot Agent, a Python platform for automating browser tasks using AI agents.

**Architecture:**
- 6 specialized agents implementing a BaseAgent Protocol (PEP 544)
- Workflow definitions in YAML (navigate, click, type, extract steps)
- Two-tier element finding: CSS selectors -> Claude vision API fallback
- Pipeline orchestrator chains agents with input mapping between steps
- FastAPI REST API + WebSocket for checkpoint approvals

**Tech stack:**
- Python 3.12 with full type hints (mypy strict)
- Playwright for browser control
- Anthropic Claude Sonnet 4 for vision fallback
- FastAPI + Pydantic v2 for API layer
- SQLAlchemy 2.0 async + PostgreSQL/SQLite
- Celery + Redis for background execution
- 490+ tests, 84% coverage

**Interesting patterns:**
- `BaseAgent` is a `runtime_checkable Protocol` — any class with the right methods is an agent, no inheritance needed
- Workflows use `{{variable}}` template syntax resolved at runtime
- Recovery engine has three tiers: retry -> LLM adapt -> escalate to human
- Session pool manages browser instances with lazy creation and idle cleanup
- All components implement `get_stats()` and `get_lessons()` for observability

**What I learned:**
- Deferred imports are essential when some deps (Celery, Playwright) might not be installed
- asyncio.Lock is critical for session pool — Playwright isn't thread-safe
- Claude's vision API is surprisingly good at finding UI elements from screenshots

Happy to discuss the architecture. PRs welcome.

GitHub: [LINK]
