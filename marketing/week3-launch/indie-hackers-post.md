# Indie Hackers Post

**Title:** I built an AI agent platform that automates browser tasks — 6 agents, 26 workflows, open source

---

Hey IH,

I've been building WebPilot Agent for the past 6 months. It's an open-source Python platform that automates repetitive browser tasks using AI.

**The origin story:** I was launching my third SaaS project in two months and realized I'd spent 6+ hours total just clicking through Clerk, Supabase, Vercel, and Stripe dashboards — doing the exact same setup steps each time. So I built a tool that does it for me.

**What it does today:**

It has 6 specialized agents:

1. **DevOps** — sets up Clerk + Supabase + Vercel + Stripe + GitHub in 10 minutes
2. **Research** — automated competitor analysis, lead research, market validation
3. **Sales** — LinkedIn outreach, CRM entry, email campaigns
4. **Marketing** — social posting, SEO audits, blog outline research
5. **Finance** — invoice tracking, revenue dashboards, subscription audits
6. **Manager** — chains agents into multi-step pipelines

**How it works:**

Workflows are YAML files. The agent uses Playwright to control a real browser. When a CSS selector fails (websites change constantly), it uses Claude's vision API to look at a screenshot and find the element. Human checkpoints pause before any critical action.

**Technical decisions I made:**

- **Python over Node.js** — better LLM SDK ecosystem, Playwright has first-class Python support
- **YAML workflows over code** — anyone can define new automations without writing Python
- **Protocol-based agents (PEP 544)** — any class with the right methods is an agent, no inheritance
- **AI vision as fallback, not primary** — CSS selectors are fast and free, vision API is only the safety net
- **Human-in-the-loop always** — agents should assist, not replace judgment

**Numbers:**
- 490+ tests, 84% coverage
- 26 workflow recipes
- 4 built-in multi-agent pipelines
- MIT license

**What's next:**
- Dashboard UI for checkpoint approvals
- Custom pipeline builder (YAML-defined)
- Community workflow marketplace

I'd love your feedback. What workflows would you find useful? What's missing?

GitHub: [LINK]
