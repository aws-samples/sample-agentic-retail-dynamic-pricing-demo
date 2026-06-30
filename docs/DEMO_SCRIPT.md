# Dynamic Pricing for Retail — Demo Script (5 minutes)

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

- **Stats cards** — "The system completes in under 2 minutes, generates 3 ranked scenarios per cycle, enforces 4 guardrail policies, and uses 6 AI agents on AgentCore Runtime."
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

> "In under 2 minutes, we have 3 ranked scenarios. Let's look at them."

**Action:** Expand the scenarios table. Point out:

- **Rank 1 (HIGH risk)** — "Aggressive Growth strategy. Higher prices where demand supports it. Requires human justification of 50+ characters."
- **Rank 2 (MEDIUM risk)** — "Balanced Optimization. Moderate adjustments. Needs human review."
- **Rank 3 (LOW risk)** — "Conservative Protection. Minimal changes, protects margins. In Straight-Through Processing mode, this would be auto-approved."

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
- **Revenue by Category bar** — shows financial impact across product lines

---

### Part 8: Revert Capability (15 seconds)

**What to say:**

> "And if a pricing decision needs to be rolled back, every approved scenario has a 'Revert Prices' button that instantly restores products to their previous prices. Full undo capability."

---

## Key Talking Points

| Traditional Process | This Solution |
|---|---|
| 6-10 weeks | < 2 minutes |
| 3-5 scenarios in Excel | 3 AI-generated ranked scenarios |
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
