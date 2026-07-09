# CCOE Dynamic Pricing Solution for Retail Transformation — Demo Script (8-9 minutes)

## Overview

This demo shows how AI agents autonomously transform retail pricing from a 6-10 week manual process into a automated workflow completing in under 2 minutes. The system uses Amazon Bedrock AgentCore to run 6 specialized AI agents that gather market intelligence, analyze demand, and generate optimized pricing recommendations — with human-in-the-loop approval for high-risk decisions and fully autonomous execution for low-risk changes.

---

## Setup Before Demo

- **Dashboard URL:** `https://<DASHBOARD_CLOUDFRONT_DOMAIN>`
- **Storefront URL:** `https://<STOREFRONT_CLOUDFRONT_DOMAIN>`
- **Login:** `<COGNITO_DEMO_USER>` / `<COGNITO_DEMO_PASSWORD>`
- Open both URLs in separate browser tabs
- Log into the Dashboard

---

## Demo Flow

### Part 1: The Problem (30 seconds)

**What to say:**

> "Today, retail pricing decisions take 6-10 weeks. Analysts manually gather data from ERP systems, competitor websites, and market reports. They build 3-5 scenarios in Excel, present 20-30 slides to a pricing committee, and then manually upload prices to multiple systems. By the time prices go live, market conditions have already shifted."

> "We've built a system that does this in under a minute using 6 specialized AI agents running on Amazon Bedrock AgentCore."

---

### Part 2: System Overview (30 seconds)

**Action:** Click the **Overview** tab on the Dashboard.

**What to point out:**

- **Stats cards** — "The system completes in under 2 minutes, generates 5 ranked scenarios per cycle, enforces 4 guardrail policies, and uses 6 AI agents on AgentCore Runtime."
- **Architecture panel** — "Built on Amazon Bedrock AgentCore with Strands Agents SDK, using Claude Sonnet 4 for analysis and Claude Opus 4 for complex reasoning."
- **Data Sources panel** — "Four MCP Servers provide real-time data: Competitor API for price monitoring, ERP/POS for sales history and inventory, Market Signals for trends, and Cost & Finance for margins."
- **Compliance panel** — "Bedrock Guardrails block anti-competitive strategies. Every decision is fully auditable."

---

### Part 3: Run a Simulation — Competitor Price War (2 minutes)

**Action:** Click the **Simulations** tab.

**What to say:**

> "Let's simulate a competitor price war. A major competitor just slashed prices by 15% on beverages. Let's see how the AI responds."

**Action:** On the "Competitor Price War" card, leave the default "Grocery > Beverages" selected. Click **"Run Simulation →"**.

**What happens (narrate as it progresses):**

> "The system immediately triggers the orchestrator agent. Watch the pipeline on the left..."

**Point out the Pipeline Sidebar as each step lights up:**

1. **Cycle Triggered** (green) — "The pricing request is logged with full traceability."
2. **Orchestrator** (blue, running) — "The orchestrator coordinates all downstream agents."
3. **Competitive Intelligence** (blue) — "This agent is analyzing competitor pricing data via the MCP Server."
4. **Demand Forecasting** (blue) — "Simultaneously, this agent calculates price elasticity from ERP/POS data."
5. **Market Intelligence** (blue) — "And this one assesses market trends and consumer sentiment."
6. **Knowledge Base Query** (blue) — "Historical pricing patterns are retrieved."
7. **Strategy Synthesis** (blue) — "Now all intelligence is combined to generate pricing scenarios."
8. **Guardrail Validation** (green) — "Amazon Bedrock Guardrails verify no anti-competitive strategies."
9. **Implementation** (amber) — "Waiting for human approval — this is the human-in-the-loop step."

> "In under 2 minutes, we have 5 ranked scenarios. Let's look at them."

**Action:** Expand the scenarios table. Point out:

- **Rank 1 (HIGH)** — "Aggressive Growth. Largest price move aligned with your objective. Requires human approval with 50+ character justification."
- **Rank 2 (HIGH)** — "Market Share Capture. Volume-focused pricing, slightly less aggressive. Also requires justification."
- **Rank 3 (MEDIUM)** — "Balanced Optimization. Moderate adjustments balancing all factors. Needs human review within 4 hours."
- **Rank 4 (MEDIUM)** — "Margin Protection. Profit-preserving adjustments. Also needs human review."
- **Rank 5 (LOW)** — "Conservative Protection. Minimal, safe changes. Auto-approved via Straight-Through Processing."

**Action:** Click "Details" on the Rank 2 scenario. Point out:

- **Price Changes** — "Each product shows current price, new recommended price, and the percentage change. Product names are clearly identified."
- **Contributing Factors** — "Competitive factors from the Competitor API, demand signals from ERP/POS, market conditions from Market Signals."
- **AI Decision Rationale** — "The AI explains WHY it made this recommendation — what data it used, what strategy it applied."
- **Guardrail Results** — "All compliance checks passed: minimum margin, maximum price change, MAP compliance, channel consistency, and Bedrock Guardrail policy."

**Action:** Type a comment like "Approved: competitive response needed to maintain market share" and click **Approve**.

> "The approval is recorded with who approved it, when, and why. The Implementation Monitoring agent now executes the price changes."

---

### Part 4: Verify on Storefront (30 seconds)

**Action:** Switch to the Storefront tab.

**What to say:**

> "Let's check the consumer-facing storefront."

**Action:** Refresh the storefront page. Point out that the beverage product prices have updated.

> "The prices are now live. The entire process — from competitive threat detection to price update on the storefront — took under a minute. Traditionally this would take 6-10 weeks."

---

### Part 5: Straight-Through Processing (1 minute)

**Action:** Go back to Dashboard → Simulations tab. Click **"Straight-Through Processing"** (leave default "Home & Garden > Lighting").

**What to say:**

> "For low-risk, routine pricing adjustments, the system can operate fully autonomously — no human needed. This is Straight-Through Processing."

**Action:** Watch the pipeline. All steps go green including Implementation.

> "Notice the pipeline — ALL steps completed automatically, including Implementation. No human approval was needed."

**Action:** Expand the scenarios. Point out the Approval column:

> "The LOW risk scenario was auto-approved by the system. It shows '⚡ Auto (STP)' — the AI determined this was safe to execute without human intervention because it met all business rules: minimum margin maintained, price change within bounds, MAP compliance verified."

> "This is the vision from the AWS guidance paper: low-risk changes are auto-implemented, while only exceptions are routed to humans."

---

### Part 6: Guardrails Enforcement Demo (1 minute)

**Action:** Go back to Dashboard → Simulations tab. Scroll down to the **"🛡️ Guardrails Enforcement"** section.

**What to say:**

> "Now let's see how the system enforces compliance. These aren't just guidelines — they're structural guardrails that physically prevent non-compliant pricing."

**Action:** Click **"🛡️ Test Guardrail →"** on the **"Below-Cost Rejection"** card.

> "Here we're trying to price Wireless Earbuds at $55 — but the manufacturing cost is $71.50. The system immediately blocks this."

**Point out the result:**
- Rule: `below-cost`
- Status: `✗ BLOCKED`
- Reason: "Price $55.00 is below total unit cost $71.50"

**Action:** Click **"🛡️ Test Guardrail →"** on the **"MAP Violation"** card.

> "Now we're trying to advertise a Smart Watch at $249.99, but the manufacturer's Minimum Advertised Price is $279.99. Blocked instantly."

**Action:** Click **"🛡️ Test Guardrail →"** on the **"Price Fixing Attempt"** card.

> "And if someone tries to use the system for price coordination with competitors — that's a per se illegal Sherman Act violation. Bedrock Guardrails block it at the model level before any pricing logic even runs."

> "These guardrails ensure regulatory compliance by design — FTC, Robinson-Patman Act, EU Omnibus Directive. Every check is recorded in the audit trail."

---

### Part 7: Audit Trail & Analytics (30 seconds)

**Action:** Click the **Audit Trail** tab.

**What to say:**

> "Every pricing decision is recorded with full traceability for regulatory compliance."

**Point out:**

- Timestamp, pricing group, objectives, status, approval status for each cycle
- Click "Expand" on one row to show the full audit detail: cycle ID, requester, constraints, scenarios with AI rationale, guardrail results, approval comments, and price changes

**Action:** Click the **Analytics** tab.

> "Financial impact is tracked in real-time. Projected revenue, average margin, automation rate, and approval distribution — all computed from actual pricing decisions."

**Point out the charts:**

- **Approval Distribution donut** — shows the balance between auto-approved and human-approved
- **Risk Classification donut** — shows the system generates safe recommendations
- **Revenue by Category** — expandable tree showing revenue by category, click to drill into subcategories (e.g., Electronics → Audio, Wearables, Tablets)

**Action:** Click the **Performance by Category** expandable tree rows.

> "This drills down three levels: Category → Subcategory → Individual Product. Each row shows projected revenue, average margin, number of price changes, and average price change percentage. Click Electronics to expand into Audio, Wearables, Tablets — then click Audio to see individual products like ProSound Earbuds."

---


### Part 8: Product Catalog & Unit Economics (30 seconds)

**Action:** Click the **Product Catalog** tab.

**What to say:**

> "Before running a pricing cycle, let me show you the data the AI works with. This is the full product catalog with unit economics -- cost structure, margins, inventory levels, and pricing boundaries."

**Point out:**

- **KPI cards** -- total products, average gross margin, low-stock items, total inventory value
- **Table columns** -- price, unit cost, margin %, MAP floor, inventory units, days of supply, stock health

**Action:** Click on a product row (e.g., FitTrack Pro Smartwatch) to expand it.

> "Each product expands to show three panels: cost breakdown (materials, labor, overhead, shipping), inventory distribution across warehouses and stores, and pricing boundaries showing the guardrail floors."

> "Notice products with LOW stock health. When we run a pricing cycle, the AI uses this signal to recommend a price increase for constrained inventory and markdown recommendations for excess stock."

---

### Part 9: Predictions & What-If Analysis (30 seconds)

**Action:** Click the **Predictions** tab.

**What to say:**

> "The Price Prediction Simulator lets you explore pricing scenarios interactively without running a full agent pipeline."

**Action:** Select a category (e.g., Electronics), select a scenario preset (e.g., "Competitor Price War"), click "Run Simulation".

> "This shows how the AI scores four market factors — Competitive Pressure, Demand Signal, Margin Constraint, and Market Intelligence — each with transparent sub-component scoring. Click any factor to expand and see the exact data sources and formulas."

**Action:** Scroll down to the **What-If Analysis** section. Select "Electronics" category, then adjust the "Competitor Price Change" slider to -15%.

> "The What-If Analysis lets you adjust market conditions and see real-time price impact on every product in the category. The 'Price Change' column shows the percentage shift from current catalog price given those conditions. In production, these shifts would trigger an automated re-evaluation."

---

### Part 10: Operations View — TCO & Scheduling (30 seconds)

**Action:** Log in as the Operations user (or switch if already logged in). Click the **Ops** tab, then select the **TCO** sub-tab.

**What to say:**

> "The Operations view shows real AWS cost data. Per-cycle breakdown shows each component: orchestrator reasoning, intelligence agents, strategy synthesis, guardrail evaluation, agent compute, and API infrastructure — totaling about $0.25 per complete pricing cycle."

**Action:** Point out the **Scaling Projections** table.

> "The scaling projections show how costs scale linearly with volume. These are based on the observed $0.247/cycle cost extrapolated to pilot, production, and enterprise volumes. The note explains the methodology and assumptions clearly."

**Action:** Click the **Architecture** sub-tab briefly, then click the **Metrics** sub-tab.

> "Live CloudWatch metrics for the deployed infrastructure — Lambda invocations, DynamoDB capacity, API Gateway requests."

**Action:** Navigate to the **Scheduling** tab (main navigation).

> "The Intelligent Pricing Scheduler configures autonomous pricing operations. Schedule Configuration shows three tiers — Daily Price Review runs every weekday morning, Category Optimization rotates through categories weekly, and Strategic Review runs monthly for executive reporting."

**Point out:** Each schedule has a description explaining what it does, when it runs, and what analysis it performs.

> "Below, Event-Driven Triggers arm the system to respond to market conditions automatically — competitor price drops, inventory thresholds, demand spikes. And the Execution Rules panel shows risk-based routing: LOW risk auto-approves, MEDIUM gets a 4-hour approval window, HIGH escalates to the Pricing Manager."

---

### Part 11: Revert Capability (15 seconds)

**What to say:**

> "And if a pricing decision needs to be rolled back, every approved scenario has a 'Revert Prices' button that instantly restores products to their previous prices. Full undo capability."

---

## Key Talking Points

| Traditional Process | This Solution |
|---|---|
| 6-10 weeks | < 2 minutes |
| 3-5 scenarios in Excel | 5 AI-generated ranked scenarios |
| Manual data gathering | 4 MCP Servers (real-time) |
| Monthly pricing committee | Instant HITL or auto-approval |
| Manual price upload | Autonomous implementation |
| No audit trail | Full decision traceability |
| No guardrails | Bedrock Guardrails (4 policies) |

## Architecture Highlights to Mention

- **Amazon Bedrock AgentCore** — serverless runtime for all 6 agents, auto-scaling, pay-per-use
- **Strands Agents SDK** — open-source framework for building the agents
- **AgentCore Gateway** — 4 MCP Server targets for enterprise system integration
- **AgentCore Memory** — provisioned for cross-cycle learning (future enhancement)
- **Bedrock Guardrails** — prevents predatory pricing, price fixing, discrimination, gouging
- **Claude Sonnet 4 / Opus 4** — foundation models for analysis and complex reasoning
- **CDK Infrastructure** — fully reproducible, one-command deployment

---

## If Asked...

**"Is this using real data?"**
> "The MCP Servers generate realistic randomized data with ±20% variance to simulate real-world market volatility. In production, these would connect to actual ERP systems, competitor APIs, and market data feeds."

**"How does it handle compliance?"**
> "Three layers: (1) Bedrock Guardrails block anti-competitive strategies at the model level, (2) application-level business rules enforce margin floors and price ceilings, (3) full audit trail with decision traceability for regulatory examination."

**"What about the learning capability mentioned in the guidance paper?"**
> "AgentCore Memory is provisioned. The next phase adds episodic memory so agents learn from past pricing decisions — which strategies worked in which market conditions — and improve recommendations over time."

**"Can this scale to hundreds of thousands of SKUs?"**
> "Yes. AgentCore Runtime auto-scales. The architecture uses a tiered approach: routine adjustments via deterministic rules, complex scenarios via the multi-agent system. Sessions are organized at the pricing-group level for coherent cross-product decisions."
