# I Automated My Entire SaaS Stack Setup — Here's How

Every new project starts the same way. You open Clerk, create an app, configure Google and email auth, copy two API keys. Then Supabase — create a project, wait two minutes for provisioning, navigate to settings, copy three keys. Vercel — import your repo, set the framework, deploy, wait. Stripe — find your API keys page, reveal the secret key, create a webhook endpoint, copy the signing secret.

Two hours. Every single time.

I've launched dozens of projects. The setup is always the same steps, the same dashboards, the same copy-paste dance. So I built a tool to do it for me.

## What WebPilot Agent Does

WebPilot Agent is an open-source Python platform that controls a real browser to automate repetitive web tasks. It navigates dashboards, clicks buttons, fills forms, and extracts data — with human checkpoints at every critical step.

Think of it as a junior DevOps engineer who follows instructions perfectly, never forgets a step, and always asks before doing anything irreversible.

```bash
webpilot run full-saas-setup \
  --var project_name=MyApp \
  --var repo_name=my-app
```

This single command runs five workflows in sequence:

1. **GitHub** — creates a private repo with README and .gitignore
2. **Clerk** — creates an app, configures Google + email auth, extracts API keys
3. **Supabase** — creates a project, waits for provisioning, extracts URL + anon key + service role key
4. **Stripe** — extracts publishable and secret keys, sets up a webhook endpoint
5. **Vercel** — imports the GitHub repo, deploys, extracts the live URL

At the end, you get all your environment variables printed in the terminal, ready to paste into `.env`.

## How It Works Under the Hood

The architecture has four layers:

**Workflow YAML** — Each setup task is defined as a YAML recipe with steps: navigate, click, type, extract, checkpoint. No code to write — just declare what needs to happen.

```yaml
steps:
  - type: navigate
    url: https://dashboard.clerk.com
  - type: checkpoint
    message: "Ready to create Clerk app. Approve?"
    screenshot: true
  - type: click
    selector: "button:has-text('Add application')"
    fallback_strategy: llm_vision
  - type: extract
    selector: "code:has-text('pk_')"
    variable: NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
```

**Two-tier element finding** — First, it tries CSS selectors (fast, deterministic). If the selector fails (because the website updated their UI), it falls back to Claude's vision API — takes a screenshot, asks "where's the Create button?", and gets a new selector. This makes it resilient to UI changes.

**Human checkpoints** — At critical moments (before creating an account, before extracting keys, before deploying), the agent pauses and shows you a screenshot. You approve or reject. No autonomous actions on sensitive operations.

**Pipeline system** — The Manager Agent chains individual workflows into multi-step pipelines. Data flows between steps — the GitHub repo URL from step 1 feeds into the Vercel deploy in step 5.

## Before vs After

| Task | Manual | WebPilot |
|------|--------|----------|
| Clerk setup | 15 min | 2 min |
| Supabase setup | 20 min | 3 min |
| Stripe setup | 15 min | 2 min |
| Vercel deploy | 15 min | 2 min |
| GitHub repo | 10 min | 1 min |
| **Total** | **75-120 min** | **10 min** |

And the real savings compound. Two projects a month means 48 hours saved per year. That's a full work week back.

## Getting Started

```bash
# Clone and install
git clone [REPO_URL]
cd webpilot-agent
pip install -e ".[dev]"
playwright install chromium

# Configure
cp .env.example .env
# Add your Anthropic API key ($5 credit from console.anthropic.com)

# Store credentials
webpilot creds set clerk_email your@email.com
webpilot creds set clerk_password --secret

# Dry run first (see the steps without launching a browser)
webpilot run clerk-setup --var project_name=TestApp --dry-run

# Real run
webpilot run clerk-setup --var project_name=TestApp
```

The `--dry-run` flag shows you every step the agent will take before it does anything. When you're ready, remove the flag and approve the checkpoints.

## What's Next

WebPilot isn't just a DevOps tool. It has six specialized agents — Research, Sales, Marketing, Finance, and a Manager that chains them together. But that's a story for another post.

Star it on GitHub: [LINK]

If you've ever wasted an afternoon on SaaS setup, give it a try. I'd love your feedback.
