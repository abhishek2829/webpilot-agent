# Product Hunt Launch Content

---

## Tagline (under 60 chars)
AI browser agents that automate the web tasks you hate

## Description (under 260 chars)
WebPilot Agent is an open-source platform with 6 AI agents that automate browser tasks — SaaS setup, competitor research, LinkedIn outreach, CRM entry, SEO audits, invoice tracking — with human approval at every critical step.

## Categories
- Productivity
- Developer Tools
- Artificial Intelligence
- SaaS
- Open Source

## Key Features to Highlight
1. **6 Specialized Agents** — DevOps, Research, Sales, Marketing, Finance, and a Manager that chains them together
2. **26 Ready-to-Use Workflows** — From Clerk setup to LinkedIn outreach to revenue dashboards
3. **Human-in-the-Loop** — Pauses for your approval before any critical action. You stay in control.
4. **AI Vision Fallback** — When CSS selectors fail, Claude looks at the screenshot and adapts. Works even when websites change their UI.
5. **Multi-Agent Pipelines** — Chain agents together: "Research company -> Find CTO -> Connect on LinkedIn -> Log in CRM"

## Gallery Screenshots (what to capture)
1. Terminal showing `webpilot run full-saas-setup` with extracted API keys
2. Browser automation in action — navigating Clerk dashboard
3. Checkpoint prompt with screenshot asking for approval
4. API docs page (Swagger UI at /docs) showing all endpoints
5. Pipeline execution summary showing 5 steps completed

## Maker Comment (first comment)

Hey Product Hunt! I'm Abhishek, and I built WebPilot Agent because I was tired of spending 2 hours setting up Clerk + Supabase + Vercel + Stripe every time I launched a new project.

The idea is simple: what if an AI agent could navigate dashboards, click buttons, fill forms, and extract API keys — but always pause for your approval before doing anything irreversible?

That's WebPilot. It uses Playwright for browser control and Claude's vision API as a fallback when selectors fail (websites change their UI all the time).

What started as a DevOps tool grew into a full platform with 6 agents:

- **DevOps Agent** — sets up your entire SaaS stack in 10 minutes
- **Research Agent** — competitor analysis, lead research, market validation
- **Sales Agent** — LinkedIn outreach, CRM data entry, email campaigns
- **Marketing Agent** — social posting, SEO audits, newsletter setup
- **Finance Agent** — invoice tracking, revenue dashboards, subscription audits
- **Manager Agent** — chains agents into multi-step pipelines

It's 100% open source (Python, MIT license). 490+ tests. Production-ready with PostgreSQL, Redis, and Celery support.

I'd love your feedback. What workflows would you add? What's missing?

Star it on GitHub: [LINK]

## Upvote Request Template

Subject: I'm launching on Product Hunt today — would love your support

Hey [Name],

I'm launching WebPilot Agent on Product Hunt today. It's an open-source AI platform that automates repetitive browser tasks — SaaS setup, research, sales outreach, and more.

If you have 30 seconds, an upvote would mean a lot: [PH LINK]

No pressure at all. Thanks for being part of this journey.

— Abhishek
