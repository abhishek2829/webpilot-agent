# Demo Video Script: Full SaaS Stack Setup in 10 Minutes

**Duration:** 90 seconds
**Thumbnail text:** "10 MIN SaaS Setup" / "One Command. Full Stack."

---

## [0:00 - 0:05] HOOK

*Screen: Terminal with cursor blinking*

**Narration:** "What if you could set up Clerk, Supabase, Vercel, and Stripe — all in one command?"

## [0:05 - 0:15] THE PROBLEM

*Screen: Rapid montage of clicking through dashboards — Clerk dashboard, Supabase project creation, Vercel deploy page, Stripe API keys page*

**Narration:** "Every new project starts the same way. Two hours of clicking through dashboards. Create app. Configure auth. Copy API keys. Deploy. Set up payments. Every. Single. Time."

## [0:15 - 0:25] THE SOLUTION

*Screen: Terminal showing the command*

**Narration:** "WebPilot does all of that in one pipeline."

*Type on screen:*
```
webpilot run full-saas-setup --var project_name=MyApp --var repo_name=my-app
```

**Narration:** "One command. Six workflows. Full stack."

## [0:25 - 0:55] THE DEMO

*Screen: Browser opens automatically, navigates to GitHub*

**Narration:** "It starts by creating your GitHub repo..."

*Screen: Browser navigates to Clerk, creates app*

**Narration:** "...sets up Clerk authentication with Google and Email providers..."

*Screen: Checkpoint appears — terminal shows "Ready to create Clerk app. Approve? [y/n]"*

**Narration:** "It pauses at checkpoints so you stay in control. You approve, it continues."

*Screen: Browser navigates to Supabase, creates project*

**Narration:** "Supabase project created. API keys extracted automatically."

*Screen: Browser navigates to Stripe, extracts API keys*

**Narration:** "Stripe keys — publishable and secret — captured and ready."

*Screen: Browser navigates to Vercel, deploys*

**Narration:** "And deployed to Vercel. Live URL extracted."

## [0:55 - 1:10] THE RESULT

*Screen: Terminal showing extracted variables*

```
Extracted Variables:
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = pk_live_xxx
  CLERK_SECRET_KEY = sk_live_xxx
  SUPABASE_URL = https://xxx.supabase.co
  SUPABASE_ANON_KEY = eyJxxx
  STRIPE_PUBLISHABLE_KEY = pk_test_xxx
  STRIPE_SECRET_KEY = sk_test_xxx
  VERCEL_DEPLOYMENT_URL = https://my-app.vercel.app

Pipeline completed in 8 minutes 42 seconds.
```

**Narration:** "All your API keys, extracted and ready to paste into your .env file. Eight minutes instead of two hours."

## [1:10 - 1:25] CTA

*Screen: GitHub repo + website URL*

**Narration:** "WebPilot Agent is open source. Star it on GitHub. Try it today. Link in the description."

## [1:25 - 1:30] END CARD

*Screen: Logo + GitHub URL + "Star on GitHub"*
