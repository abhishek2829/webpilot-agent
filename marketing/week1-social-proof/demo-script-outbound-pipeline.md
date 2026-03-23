# Demo Video Script: Automated Outbound Sales Pipeline

**Duration:** 90 seconds
**Thumbnail text:** "AI Sales Pipeline" / "Research to CRM in One Command"

---

## [0:00 - 0:05] HOOK

**Narration:** "Research a company, find the CTO on LinkedIn, send a connection request, log it in your CRM. One command."

## [0:05 - 0:15] THE PROBLEM

*Screen: Split screen — LinkedIn, HubSpot, company website*

**Narration:** "Outbound sales is a grind. Research the company. Find the right person. Go to LinkedIn. Send a message. Switch to HubSpot. Create a contact. Add notes. Repeat 50 times a day."

## [0:15 - 0:25] THE SOLUTION

*Screen: Terminal*

```
POST /api/pipelines/outbound-pipeline/run
{
  "parameters": {
    "company_url": "https://example.com",
    "connection_message": "Hi, loved your recent launch..."
  }
}
```

**Narration:** "WebPilot chains three agents together. Research Agent finds the company info. Sales Agent handles LinkedIn. Sales Agent logs it in your CRM."

## [0:25 - 0:55] THE DEMO

*Screen: Browser navigates to company website*

**Narration:** "Step 1 — Research Agent visits the company site. Extracts name, industry, size, key people."

*Screen: Browser navigates to LinkedIn*

**Narration:** "Step 2 — Sales Agent finds the CTO on LinkedIn."

*Screen: Checkpoint — "About to send connection request to Jane Smith, CTO. Approve?"*

**Narration:** "It pauses before sending anything. You review the profile, approve the message."

*Screen: Connection request sent*

**Narration:** "Connection sent with your personalized note."

*Screen: Browser navigates to HubSpot*

**Narration:** "Step 3 — Sales Agent creates a contact in HubSpot with all the research data attached."

## [0:55 - 1:15] THE RESULT

*Screen: Pipeline summary*

```
Pipeline: outbound-pipeline
Steps completed: 3/3
  Step 1: lead-research     -> COMPANY_NAME, KEY_PEOPLE
  Step 2: linkedin-connect  -> CONNECTION_STATUS: sent
  Step 3: crm-entry         -> CONTACT_ID: 847291

Duration: 4 minutes 12 seconds
```

**Narration:** "Three agents, one pipeline, four minutes. Now imagine running this 50 times."

## [1:15 - 1:30] CTA

**Narration:** "WebPilot Agent. Your AI sales team that never sleeps. Open source on GitHub."
