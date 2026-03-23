# WebPilot Agent — Landing Page Copy

---

## Hero Section

**Headline:** Stop clicking. Start shipping.

**Subheadline:** 6 AI agents that automate your browser tasks — SaaS setup, research, sales outreach, marketing, and finance — with human approval at every critical step.

**CTA Button:** Get Started Free

**Secondary CTA:** Star on GitHub

---

## Problem Section

### The work you shouldn't be doing manually

**Pain Point 1: SaaS Setup**
Every new project = 2 hours clicking through Clerk, Supabase, Vercel, Stripe, and GitHub dashboards. Creating accounts. Copying API keys. Configuring settings. The same steps, every single time.

**Pain Point 2: Research & Outreach**
Manual competitor research. LinkedIn prospecting one profile at a time. Copying data between browser tabs and spreadsheets. Your team spends 60% of their time on non-core work.

**Pain Point 3: Monitoring & Reporting**
Logging into Stripe to check revenue. Scrolling through invoices. Pulling analytics numbers. Repetitive data extraction from dashboards you visit daily.

---

## Solution Section

### How WebPilot works

**Step 1: Choose a workflow**
Pick from 26 pre-built workflows across 6 domains — or define your own in YAML. No code required.

**Step 2: Run one command**
```
webpilot run clerk-setup --var project_name=MyApp
```
The agent opens a real browser, navigates the dashboard, and does the work.

**Step 3: Approve and go**
At critical moments, the agent pauses and shows you a screenshot. You approve, it continues. You stay in control.

---

## Agent Showcase

### 6 agents. One platform.

**DevOps Setup Agent**
Sets up your entire SaaS stack in 10 minutes. Clerk auth, Supabase database, Vercel deployment, Stripe payments, GitHub repos, custom domains.
*6 workflows | 2+ hours saved per project*

**Research Agent**
Automates web research. Competitor pricing and features, lead research, market validation on Product Hunt and Reddit, tech stack detection, content/SEO analysis.
*5 workflows | Research 10 companies in 15 minutes*

**Sales Agent**
Handles outbound sales operations. LinkedIn connection requests, HubSpot CRM entry, email campaign setup, Calendly meeting scheduling, proposal generation.
*5 workflows | 4 minutes per prospect instead of 25*

**Marketing Agent**
Manages content and distribution. Social media posting, SEO audits with PageSpeed scores, blog outline research, newsletter platform setup, analytics extraction.
*5 workflows | Automated content operations*

**Finance Agent**
Tracks the money. Stripe invoice monitoring, payment failure alerts, expense categorization, subscription audits, revenue dashboard extraction (MRR, churn, growth).
*5 workflows | Financial visibility on autopilot*

**Manager Agent**
The orchestrator. Chains agents into multi-step pipelines with data flowing between steps. "Research company, find CTO, connect on LinkedIn, log in CRM" — one command.
*4 built-in pipelines | Custom pipeline support*

---

## Pipeline Showcase

### Multi-agent pipelines

**Full SaaS Setup**
GitHub repo -> Clerk auth -> Supabase DB -> Stripe payments -> Vercel deploy
*5 steps, 10 minutes, all API keys extracted*

**Outbound Pipeline**
Research company -> Find decision maker -> LinkedIn connect -> CRM entry
*3 steps, 4 minutes per prospect*

**Content Launch**
Research topic -> Blog outline -> Newsletter setup -> Social post
*4 steps, automated content workflow*

**Revenue Health Check**
Revenue dashboard -> Invoice tracker -> Payment monitor -> Subscription audit
*4 steps, full financial snapshot*

---

## Pricing

### Free forever. Pay for power.

**Free**
$0/month
- 3 workflow runs per month
- DevOps Agent only
- CLI access
- Community support
- Open source (MIT)

**Pro**
$49/month
- Unlimited workflow runs
- All 6 agents
- CLI + REST API
- Multi-agent pipelines
- Email support

**Team**
$199/month
- Everything in Pro
- 5 team seats
- Shared credential vault
- Custom workflow builder
- Pipeline builder
- Priority support

**Enterprise**
Custom pricing
- Unlimited seats
- Custom agent development
- Dedicated infrastructure
- SSO / SAML
- SLA guarantee
- Dedicated support engineer

---

## FAQ

**How does WebPilot control the browser?**
WebPilot uses Playwright, an open-source browser automation library by Microsoft. It controls a real Chromium browser — the same one you use daily.

**What happens when a website changes its UI?**
When a CSS selector fails, WebPilot falls back to Claude's vision API. It takes a screenshot of the page and asks Claude to find the element. This makes it resilient to UI changes without any manual maintenance.

**Is it safe? Can it do things without my approval?**
Every critical action has a human checkpoint. Before creating an account, sending a message, or deploying code, the agent pauses and shows you a screenshot. You approve or reject. Nothing happens without your explicit consent.

**How much does the Claude API cost?**
Very little. CSS selectors handle 90%+ of element finding. The vision API is only called when selectors fail — typically 0-2 times per workflow. The $5 starter credit from Anthropic lasts months.

**Can I add my own workflows?**
Yes. Workflows are YAML files. Define your steps (navigate, click, type, extract, checkpoint), point to the selectors, and the agent runs it. No Python code needed for basic workflows.

**Does it work with any website?**
Yes. Unlike API-based tools, WebPilot works with any web interface because it controls a real browser. If you can do it manually in a browser, WebPilot can automate it.

**Is it open source?**
Yes. MIT license. You can self-host, fork, modify, and contribute. The core platform is free forever. Pro/Team plans add convenience features and support.

**What's the difference between WebPilot and Selenium/Puppeteer scripts?**
Three things: (1) AI vision fallback makes it resilient to UI changes, (2) human checkpoints ensure safety, (3) the multi-agent pipeline system lets you chain workflows across domains. It's a platform, not a scripting tool.

---

## Final CTA Section

### Ready to stop clicking?

Set up your first workflow in 5 minutes. Free, open source, no credit card required.

**[Get Started Free]**    **[Star on GitHub]**    **[Read the Docs]**

---

## Footer

WebPilot Agent | Open Source (MIT) | Built with Python, Playwright, and Claude

GitHub | Documentation | Blog | Twitter | Discord

Copyright 2026 WebPilot Agent. All rights reserved.
