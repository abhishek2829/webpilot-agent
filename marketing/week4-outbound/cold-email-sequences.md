# Cold Email Sequences

---

## Sequence 1: Dev Agency Founders

### Email 1 — Initial outreach
**Subject:** How long does your team spend on client project setup?

Hi [Name],

Quick question: when your team starts a new client project, how long does the SaaS setup take? Creating the GitHub repo, configuring Clerk auth, provisioning Supabase, setting up Stripe, deploying to Vercel?

At most agencies I've talked to, it's 2-3 hours per project.

I built an open-source tool called WebPilot Agent that automates the entire setup in 10 minutes. One command, human approval at each step, all API keys extracted automatically.

Would a 10-minute demo be useful?

Best,
Abhishek

### Email 2 — Follow-up (3 days later)
**Subject:** Re: How long does your team spend on client project setup?

Hi [Name],

Just following up. Here's a quick breakdown of what WebPilot automates:

- GitHub repo creation + settings (1 min)
- Clerk auth setup + API key extraction (2 min)
- Supabase project + 3 API keys (3 min)
- Stripe keys + webhook setup (2 min)
- Vercel deploy + live URL (2 min)

Total: ~10 minutes. Your team gets a .env file with all keys ready.

Open source, MIT license. No vendor lock-in.

Happy to walk you through it if you're interested.

### Email 3 — Breakup (5 days later)
**Subject:** Last note on project setup automation

Hi [Name],

I'll keep this short — I know your inbox is full.

If automating client project setup isn't a priority right now, totally understand. But if your team ever burns a morning clicking through dashboards, here's the GitHub link: [LINK]

It's free and open source. No signup needed.

All the best with your projects.

Abhishek

---

## Sequence 2: Startup CTOs / DevOps Leads

### Email 1
**Subject:** Developer onboarding at [Company] — a quick thought

Hi [Name],

Congrats on the team growth at [Company]. When new engineers join, how long does it take to get them set up with all the SaaS accounts and API keys they need?

I built WebPilot Agent to solve this. It automates the entire developer environment setup — GitHub access, Clerk auth, Supabase DB, Stripe test mode, Vercel staging — in a single pipeline.

New engineer joins Monday morning, has all their keys by lunch. No manual dashboard clicking.

The tool is open source (Python + Playwright). 490+ tests. Production infrastructure with PostgreSQL, Redis, and Celery.

Worth a 10-minute look?

Abhishek

### Email 2 (3 days)
**Subject:** Re: Developer onboarding

Hi [Name],

One data point: the typical onboarding setup takes 4-6 hours of dashboard clicking. With WebPilot's pipeline, it's 15 minutes.

For a team hiring 2 engineers a month, that's 100+ hours saved per year.

Here's what the pipeline looks like:

```
webpilot run full-saas-setup --var project_name=NewEngineer
```

Human checkpoints at every critical step. Encrypted credential vault. Full audit trail.

If this isn't the right time, no worries. The repo is public: [LINK]

### Email 3 (5 days)
**Subject:** Closing the loop

Hi [Name],

Last email on this. If developer onboarding is already smooth at [Company], great — you're ahead of most.

If it's still a manual process, the tool is free and takes 5 minutes to try: [LINK]

Either way, best of luck with the growth.

Abhishek

---

## Sequence 3: Sales Leaders

### Email 1
**Subject:** Your SDRs are spending 60% of their time not selling

Hi [Name],

Research says SDRs spend about 65% of their time on non-selling activities — researching companies, finding contacts on LinkedIn, manual CRM data entry.

I built an AI pipeline that automates the grunt work:

1. Research Agent visits the prospect's website, extracts company info
2. Sales Agent finds the decision maker on LinkedIn, prepares a connection request
3. Sales Agent creates a HubSpot contact with all research pre-filled

Human approval before every outbound action. Your reps review and approve — the agent handles the clicking.

4 minutes per prospect instead of 25.

Worth a quick look?

Abhishek

### Email 2 (3 days)
**Subject:** Re: SDR productivity

Hi [Name],

Quick math on the outbound pipeline:

- Manual: 25 min/prospect x 50/day = 20+ hours/week on research & data entry
- WebPilot: 4 min/prospect x 50/day = 3.5 hours/week

That's 16+ hours per SDR per week freed up for actual conversations.

The tool is open source. No per-seat pricing. No vendor contract.

Happy to do a live demo with your LinkedIn and CRM. 15 minutes.

### Email 3 (5 days)
**Subject:** Final thought on sales automation

Hi [Name],

I'll stop here. If your team's outbound process is already efficient, great.

If SDRs are still spending hours on LinkedIn + CRM data entry, the tool is free: [LINK]

It works with any web interface — no API integrations needed. Just browser automation with human oversight.

All the best,
Abhishek
