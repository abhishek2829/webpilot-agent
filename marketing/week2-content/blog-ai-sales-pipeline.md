# Building an AI Sales Pipeline That Actually Works

The average SDR spends 65% of their time on non-selling activities. Research. Data entry. LinkedIn scrolling. CRM updates. The actual conversations — the part that closes deals — gets squeezed into what's left.

I built an AI sales pipeline that automates the grind and leaves the human work to humans.

## The Problem with Manual Outbound

Here's what a typical outbound workflow looks like:

1. Research the target company (5-10 min)
2. Find the right person on LinkedIn (5 min)
3. Check their recent posts for personalization hooks (5 min)
4. Send a connection request with a personalized note (2 min)
5. Switch to HubSpot, create a contact (3 min)
6. Add notes, set deal stage, log the activity (3 min)

Total: 20-30 minutes per prospect. For 50 prospects a day, that's a full week of work.

And most of it is clicking, copying, pasting, and context-switching between tabs.

## How the Outbound Pipeline Works

WebPilot's outbound pipeline chains three agents together:

```
POST /api/pipelines/outbound-pipeline/run
{
  "parameters": {
    "company_url": "https://target-company.com",
    "connection_message": "Hi, saw your recent product launch..."
  }
}
```

**Step 1: Research Agent** visits the company website. It extracts the company name, industry, size, key people, and recent news. Structured data, not a wall of text.

**Step 2: Sales Agent** takes the key person from step 1, finds them on LinkedIn, and prepares a connection request with your message. It pauses here — you see the profile, review the message, and approve before anything is sent.

**Step 3: Sales Agent** creates a contact in HubSpot with all the research data pre-filled. Company name, person's title, LinkedIn URL, industry — all attached to the contact record.

Four minutes per prospect. With human approval at the critical moment.

## Why Human-in-the-Loop Matters

I deliberately designed this NOT to be fully autonomous. Here's why:

**Sales is personal.** A generic "I'd love to connect" message gets ignored. The agent finds the prospect, but YOU personalize the message based on what you see on their profile.

**Mistakes are expensive.** One wrong connection request to a CEO with a typo in their name damages your brand. The checkpoint lets you catch errors before they go out.

**Trust is everything.** When you tell a prospect "I saw your recent launch" — it should be true. The checkpoint lets you verify the research before it becomes outreach.

The pipeline handles the clicking, typing, and tab-switching. You handle the judgment.

## The Workflow YAML

Each step is a declarative YAML recipe:

```yaml
# linkedin-connect.yaml
name: linkedin-connect
steps:
  - type: navigate
    url: "{{prospect_url}}"
  - type: checkpoint
    message: "Review this prospect profile before connecting"
    screenshot: true
  - type: click
    selector: "button:has-text('Connect')"
    fallback_strategy: llm_vision
  - type: type
    selector: "textarea[name='message']"
    text: "{{connection_message}}"
  - type: checkpoint
    message: "About to send connection. Approve?"
    screenshot: true
  - type: click
    selector: "button:has-text('Send')"
```

The `fallback_strategy: llm_vision` is the key differentiator. When LinkedIn changes their UI (which they do constantly), the agent takes a screenshot and asks Claude "where's the Connect button?" instead of failing.

## What You Can Build With This

The outbound pipeline is just the starting template. You can chain any combination:

**Investor outreach:** Research the VC firm -> find partners on LinkedIn -> connect with portfolio context

**Recruiting pipeline:** Find companies hiring your role -> identify hiring managers -> send personalized outreach

**Partnership development:** Research potential partners -> find business development contacts -> propose integration

Each pipeline is defined in Python — add steps, change the agent routing, map data between steps.

## Getting Started

```bash
pip install -e ".[dev]"
playwright install chromium

# Store your credentials (encrypted at rest)
webpilot creds set linkedin_email your@email.com
webpilot creds set linkedin_password --secret
webpilot creds set hubspot_email your@email.com
webpilot creds set hubspot_password --secret

# Run the pipeline
webpilot run linkedin-connect \
  --var prospect_url=https://linkedin.com/in/someone \
  --var connection_message="Hi, loved your recent post about..."
```

Or use the full pipeline via the API for batch processing.

## The Math

| Metric | Manual | WebPilot |
|--------|--------|----------|
| Time per prospect | 25 min | 4 min |
| Prospects per day (8hr) | 19 | 120 |
| Weekly capacity | 95 | 600 |
| Monthly pipeline | 380 | 2,400 |

The bottleneck shifts from "I don't have time to reach out" to "I need better prospect lists."

That's the right problem to have.

Star it on GitHub: [LINK]
