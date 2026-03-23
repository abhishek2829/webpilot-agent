const GITHUB_URL = "https://github.com/abhishek2829/webpilot-agent";

const agents = [
  {
    name: "DevOps Setup",
    icon: "~>",
    description: "Sets up your entire SaaS stack in 10 minutes. Clerk auth, Supabase database, Vercel deployment, Stripe payments, GitHub repos, custom domains.",
    workflows: 6,
    stat: "2+ hours saved per project",
  },
  {
    name: "Research",
    icon: "?>",
    description: "Automates web research. Competitor pricing, lead research, market validation on Product Hunt and Reddit, tech stack detection, content analysis.",
    workflows: 5,
    stat: "10 companies in 15 minutes",
  },
  {
    name: "Sales",
    icon: "$>",
    description: "Handles outbound sales. LinkedIn connections, HubSpot CRM entry, email campaign setup, Calendly scheduling, proposal generation.",
    workflows: 5,
    stat: "4 min/prospect vs 25 min",
  },
  {
    name: "Marketing",
    icon: "#>",
    description: "Content and distribution. Social media posting, SEO audits with PageSpeed scores, blog outlines, newsletter setup, analytics extraction.",
    workflows: 5,
    stat: "Automated content ops",
  },
  {
    name: "Finance",
    icon: "%>",
    description: "Tracks the money. Stripe invoice monitoring, payment alerts, expense categorization, subscription audits, revenue dashboard extraction.",
    workflows: 5,
    stat: "Financial visibility on autopilot",
  },
  {
    name: "Growth",
    icon: "^>",
    description: "Revenue engine. Finds hot leads on social platforms, qualifies prospects, runs personalized outreach campaigns, tracks pipeline and conversions.",
    workflows: 7,
    stat: "Full growth cycle automated",
  },
];

const pipelines = [
  { name: "full-saas-setup", description: "GitHub -> Clerk -> Supabase -> Stripe -> Vercel", steps: 5 },
  { name: "outbound-pipeline", description: "Research company -> Find CTO -> LinkedIn connect -> CRM entry", steps: 3 },
  { name: "content-launch", description: "Research topic -> Blog outline -> Newsletter -> Social post", steps: 4 },
  { name: "weekly-growth-cycle", description: "Find leads -> Qualify -> Outreach -> Content -> Track", steps: 6 },
];

const pricing = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    features: ["3 workflow runs/month", "DevOps Agent only", "CLI access", "Community support", "Open source (MIT)"],
    cta: "Get Started",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "$49",
    period: "/month",
    features: ["Unlimited workflow runs", "All 7 agents", "CLI + REST API", "Multi-agent pipelines", "Email support"],
    cta: "Start Pro Trial",
    highlighted: true,
  },
  {
    name: "Team",
    price: "$199",
    period: "/month",
    features: ["Everything in Pro", "5 team seats", "Shared credential vault", "Custom workflow builder", "Priority support"],
    cta: "Start Team Trial",
    highlighted: false,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    features: ["Unlimited seats", "Custom agent development", "Dedicated infrastructure", "SSO / SAML", "SLA guarantee"],
    cta: "Contact Sales",
    highlighted: false,
  },
];

const faqs = [
  {
    q: "How does WebPilot control the browser?",
    a: "WebPilot uses Playwright, an open-source browser automation library by Microsoft. It controls a real Chromium browser -- the same one you use daily.",
  },
  {
    q: "What happens when a website changes its UI?",
    a: "When a CSS selector fails, WebPilot falls back to Claude's vision API. It takes a screenshot and asks Claude to find the element. No manual maintenance needed.",
  },
  {
    q: "Is it safe? Can it do things without my approval?",
    a: "Every critical action has a human checkpoint. Before creating an account, sending a message, or deploying code, the agent pauses and shows you a screenshot. Nothing happens without your explicit consent.",
  },
  {
    q: "How much does the Claude API cost?",
    a: "Very little. CSS selectors handle 90%+ of cases. The vision API is only called when selectors fail -- typically 0-2 times per workflow. The $5 starter credit lasts months.",
  },
  {
    q: "Can I add my own workflows?",
    a: "Yes. Workflows are YAML files. Define your steps, point to the selectors, and the agent runs it. No Python code needed for basic workflows.",
  },
  {
    q: "Does it work with any website?",
    a: "Yes. Unlike API-based tools, WebPilot controls a real browser. If you can do it manually, WebPilot can automate it.",
  },
  {
    q: "What's the difference from Selenium scripts?",
    a: "Three things: AI vision fallback makes it resilient to UI changes, human checkpoints ensure safety, and multi-agent pipelines let you chain workflows across domains.",
  },
  {
    q: "Is it open source?",
    a: "Yes. MIT license. Self-host, fork, modify, contribute. The core platform is free forever. Pro/Team plans add convenience and support.",
  },
];

export default function Home() {
  return (
    <main>
      {/* Nav */}
      <nav className="fixed top-0 w-full z-50 bg-gray-950/80 backdrop-blur-md border-b border-gray-800">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <span className="text-xl font-bold tracking-tight">
            <span className="text-emerald-400">Web</span>Pilot
          </span>
          <div className="flex items-center gap-6">
            <a href="#agents" className="text-sm text-gray-400 hover:text-white transition">Agents</a>
            <a href="#pipelines" className="text-sm text-gray-400 hover:text-white transition">Pipelines</a>
            <a href="#pricing" className="text-sm text-gray-400 hover:text-white transition">Pricing</a>
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm bg-gray-800 hover:bg-gray-700 px-4 py-2 rounded-lg transition"
            >
              GitHub
            </a>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight leading-tight">
            Stop clicking.
            <br />
            <span className="text-emerald-400">Start shipping.</span>
          </h1>
          <p className="mt-6 text-xl text-gray-400 max-w-2xl mx-auto">
            7 AI agents that automate your browser tasks -- SaaS setup, research, sales outreach,
            marketing, and finance -- with human approval at every critical step.
          </p>
          <div className="mt-10 flex flex-col sm:flex-row gap-4 justify-center">
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="px-8 py-4 bg-emerald-500 hover:bg-emerald-400 text-gray-950 font-semibold rounded-xl text-lg transition"
            >
              Get Started Free
            </a>
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="px-8 py-4 bg-gray-800 hover:bg-gray-700 rounded-xl text-lg transition"
            >
              Star on GitHub
            </a>
          </div>
          <div className="mt-8 flex justify-center gap-8 text-sm text-gray-500">
            <span>7 Agents</span>
            <span>33 Workflows</span>
            <span>8 Pipelines</span>
            <span>524+ Tests</span>
          </div>
        </div>
      </section>

      {/* Code Demo */}
      <section className="pb-20 px-6">
        <div className="max-w-3xl mx-auto">
          <div className="bg-gray-900 rounded-2xl border border-gray-800 p-6 font-mono text-sm">
            <div className="flex gap-2 mb-4">
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <div className="w-3 h-3 rounded-full bg-yellow-500" />
              <div className="w-3 h-3 rounded-full bg-green-500" />
            </div>
            <div className="text-gray-400">
              <span className="text-emerald-400">$</span> webpilot run full-saas-setup --var project_name=MyApp
            </div>
            <div className="mt-3 text-gray-500">
              Running pipeline: GitHub -&gt; Clerk -&gt; Supabase -&gt; Stripe -&gt; Vercel
            </div>
            <div className="mt-2 text-yellow-400">
              [checkpoint] Ready to create Clerk app &apos;MyApp&apos;. Approve? [y/n] <span className="text-emerald-400">y</span>
            </div>
            <div className="mt-2 text-gray-500">
              Clerk app created. Extracting API keys...
            </div>
            <div className="mt-2 text-yellow-400">
              [checkpoint] Extract API keys? Approve? [y/n] <span className="text-emerald-400">y</span>
            </div>
            <div className="mt-3 text-emerald-400">
              Pipeline completed in 8m 42s. Extracted 8 API keys.
            </div>
            <div className="mt-2 text-gray-400">
              NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = pk_live_xxx...
              <br />
              SUPABASE_URL = https://xxx.supabase.co
              <br />
              STRIPE_SECRET_KEY = sk_test_xxx...
              <br />
              VERCEL_DEPLOYMENT_URL = https://myapp.vercel.app
            </div>
          </div>
        </div>
      </section>

      {/* Problem */}
      <section className="py-20 px-6 border-t border-gray-800">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">The work you shouldn&apos;t be doing manually</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
              <div className="text-2xl mb-3">2 hours</div>
              <h3 className="font-semibold mb-2">SaaS Setup</h3>
              <p className="text-gray-400 text-sm">
                Clicking through Clerk, Supabase, Vercel, Stripe, and GitHub dashboards. Same steps, every project.
              </p>
            </div>
            <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
              <div className="text-2xl mb-3">60%</div>
              <h3 className="font-semibold mb-2">Non-selling time</h3>
              <p className="text-gray-400 text-sm">
                SDRs spend most of their time researching, copy-pasting, and doing CRM data entry instead of having conversations.
              </p>
            </div>
            <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
              <div className="text-2xl mb-3">Daily</div>
              <h3 className="font-semibold mb-2">Dashboard monitoring</h3>
              <p className="text-gray-400 text-sm">
                Logging into Stripe, checking invoices, pulling analytics. Repetitive data extraction from the same dashboards.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-20 px-6 border-t border-gray-800">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">How WebPilot works</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="w-12 h-12 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto text-xl font-bold mb-4">1</div>
              <h3 className="font-semibold mb-2">Choose a workflow</h3>
              <p className="text-gray-400 text-sm">Pick from 33 pre-built workflows or define your own in YAML. No code required.</p>
            </div>
            <div className="text-center">
              <div className="w-12 h-12 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto text-xl font-bold mb-4">2</div>
              <h3 className="font-semibold mb-2">Run one command</h3>
              <p className="text-gray-400 text-sm">The agent opens a browser, navigates dashboards, and does the work. AI vision adapts when UIs change.</p>
            </div>
            <div className="text-center">
              <div className="w-12 h-12 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto text-xl font-bold mb-4">3</div>
              <h3 className="font-semibold mb-2">Approve and go</h3>
              <p className="text-gray-400 text-sm">At critical moments, the agent pauses with a screenshot. You approve, it continues. You stay in control.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Agents */}
      <section id="agents" className="py-20 px-6 border-t border-gray-800">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">7 agents. One platform.</h2>
          <p className="text-center text-gray-400 mb-12">Each agent specializes in a domain. The Manager chains them together.</p>
          <div className="grid md:grid-cols-2 gap-6">
            {agents.map((agent) => (
              <div key={agent.name} className="bg-gray-900 rounded-xl p-6 border border-gray-800 hover:border-emerald-500/50 transition">
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-emerald-400 font-mono text-lg">{agent.icon}</span>
                  <h3 className="font-semibold text-lg">{agent.name} Agent</h3>
                  <span className="ml-auto text-xs text-gray-500 bg-gray-800 px-2 py-1 rounded">{agent.workflows} workflows</span>
                </div>
                <p className="text-gray-400 text-sm mb-3">{agent.description}</p>
                <p className="text-emerald-400 text-sm font-medium">{agent.stat}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pipelines */}
      <section id="pipelines" className="py-20 px-6 border-t border-gray-800">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Multi-agent pipelines</h2>
          <p className="text-center text-gray-400 mb-12">Chain agents together. Data flows between steps automatically.</p>
          <div className="grid md:grid-cols-2 gap-6">
            {pipelines.map((p) => (
              <div key={p.name} className="bg-gray-900 rounded-xl p-6 border border-gray-800">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-mono text-emerald-400">{p.name}</h3>
                  <span className="text-xs text-gray-500">{p.steps} steps</span>
                </div>
                <p className="text-gray-400 text-sm">{p.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-20 px-6 border-t border-gray-800">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Free forever. Pay for power.</h2>
          <p className="text-center text-gray-400 mb-12">Open source core. Premium features for teams.</p>
          <div className="grid md:grid-cols-4 gap-6">
            {pricing.map((plan) => (
              <div
                key={plan.name}
                className={`rounded-xl p-6 border ${
                  plan.highlighted
                    ? "bg-emerald-500/10 border-emerald-500"
                    : "bg-gray-900 border-gray-800"
                }`}
              >
                <h3 className="font-semibold text-lg mb-1">{plan.name}</h3>
                <div className="mb-4">
                  <span className="text-3xl font-bold">{plan.price}</span>
                  <span className="text-gray-400 text-sm">{plan.period}</span>
                </div>
                <ul className="space-y-2 mb-6">
                  {plan.features.map((f) => (
                    <li key={f} className="text-sm text-gray-400 flex items-start gap-2">
                      <span className="text-emerald-400 mt-0.5">+</span>
                      {f}
                    </li>
                  ))}
                </ul>
                <a
                  href={GITHUB_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`block text-center py-2 rounded-lg text-sm font-medium transition ${
                    plan.highlighted
                      ? "bg-emerald-500 hover:bg-emerald-400 text-gray-950"
                      : "bg-gray-800 hover:bg-gray-700"
                  }`}
                >
                  {plan.cta}
                </a>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-20 px-6 border-t border-gray-800">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">FAQ</h2>
          <div className="space-y-6">
            {faqs.map((faq) => (
              <div key={faq.q} className="bg-gray-900 rounded-xl p-6 border border-gray-800">
                <h3 className="font-semibold mb-2">{faq.q}</h3>
                <p className="text-gray-400 text-sm">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-20 px-6 border-t border-gray-800">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-4xl font-bold mb-4">Ready to stop clicking?</h2>
          <p className="text-gray-400 mb-8">Set up your first workflow in 5 minutes. Free, open source, no credit card required.</p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="px-8 py-4 bg-emerald-500 hover:bg-emerald-400 text-gray-950 font-semibold rounded-xl text-lg transition"
            >
              Get Started Free
            </a>
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="px-8 py-4 bg-gray-800 hover:bg-gray-700 rounded-xl text-lg transition"
            >
              Star on GitHub
            </a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-gray-800">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <span className="text-sm text-gray-500">
            <span className="text-emerald-400 font-semibold">Web</span>Pilot Agent -- Open Source (MIT)
          </span>
          <div className="flex gap-6 text-sm text-gray-500">
            <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="hover:text-white transition">GitHub</a>
            <a href={`${GITHUB_URL}#quick-start`} target="_blank" rel="noopener noreferrer" className="hover:text-white transition">Docs</a>
            <a href={`${GITHUB_URL}/issues`} target="_blank" rel="noopener noreferrer" className="hover:text-white transition">Issues</a>
          </div>
        </div>
      </footer>
    </main>
  );
}
