# Hacker News "Show HN" Post

---

## Title
Show HN: WebPilot Agent -- Open-source AI browser agents for automating web tasks

## Body

I built WebPilot Agent, an open-source Python platform that uses Playwright and Claude's vision API to automate repetitive browser tasks with human-in-the-loop checkpoints.

The problem: many SaaS tools (Clerk, Vercel, Supabase, Stripe) require clicking through dashboards for setup. No CLI, no API for initial configuration. Every new project means 2 hours of the same clicks.

WebPilot has 6 specialized agents:

- DevOps: automates SaaS stack setup (Clerk, Vercel, Supabase, Stripe, GitHub, domains)
- Research: competitor analysis, lead research, market validation
- Sales: LinkedIn outreach, CRM entry, email campaigns
- Marketing: social posting, SEO audits, analytics extraction
- Finance: invoice tracking, payment monitoring, revenue dashboards
- Manager: chains agents into multi-step pipelines

How it works:
1. Workflows are defined in YAML (navigate, click, type, extract steps)
2. Playwright controls the browser
3. CSS selectors handle 90% of element finding
4. When selectors fail, Claude's vision API looks at a screenshot and finds the element
5. Human checkpoints pause execution for approval at critical moments

Tech stack: Python 3.12, Playwright, Anthropic Claude API, FastAPI, PostgreSQL, Redis, Celery. 490+ tests.

GitHub: [LINK]

---

## Anticipated HN Comments & Responses

**"How is this different from Selenium scripts?"**
Response: Three key differences. (1) AI vision fallback — when selectors break (and they always do), Claude looks at the screenshot and finds the element. No more maintaining brittle scripts. (2) Human checkpoints — the agent pauses for approval before critical actions. (3) Multi-agent pipelines — chain workflows across different domains (research -> sales -> CRM).

**"Doesn't browser-use already do this?"**
Response: browser-use is one of our dependencies for browser control. WebPilot adds the application layer on top: workflow YAML definitions, a checkpoint system, credential vault, multi-agent architecture, REST API, and a pipeline orchestrator. It's the difference between a library and a platform.

**"What about rate limiting? LinkedIn will ban you."**
Response: The human checkpoint system naturally rate-limits. The agent pauses before every outbound action. You review and approve. It's not a bot that blasts 500 connection requests — it's an assistant that prepares one at a time for your approval.

**"Why not just use APIs directly?"**
Response: Many services don't have APIs for initial setup. You can't programmatically create a Clerk application, configure auth providers, and extract API keys through their API. You have to use the dashboard. Same with Vercel project settings, Supabase project creation, etc.

**"How do you handle CAPTCHAs?"**
Response: Currently, the checkpoint system handles this — if a CAPTCHA appears, the agent pauses at the next checkpoint and you solve it manually. For the common case (logged-in sessions with saved cookies), CAPTCHAs are rare. Future work: integrate CAPTCHA solving services.

**"What's the Claude API cost?"**
Response: Minimal. CSS selectors handle 90%+ of element finding. The vision API is only called as a fallback when selectors fail. In testing, a typical workflow makes 0-2 API calls. The $5 starter credit lasts months.
