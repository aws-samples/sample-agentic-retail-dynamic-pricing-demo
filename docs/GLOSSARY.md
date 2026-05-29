# Retail Dynamic Pricing — Glossary of Industry Terms & Abbreviations

This document provides full forms, definitions, and simple examples for all retail industry terminology, abbreviations, and technical terms used in this solution.

---

## Pricing & Cost Abbreviations

### COGS — Cost of Goods Sold
**Definition**: The total direct cost of producing or purchasing the goods that a company sells. Includes materials, labor, and manufacturing overhead — but NOT marketing, distribution, or admin costs.

**Example**: If you sell a Bluetooth Speaker for $149.99 and it costs $71.50 to manufacture (materials $45 + labor $12.50 + overhead $8.75 + shipping $5.25), your COGS is $71.50.

**In this solution**: The Cost & Finance MCP Server returns `total_unit_cost` which represents COGS. The below-cost guardrail ensures `price >= COGS`.

---

### MAP — Minimum Advertised Price
**Definition**: The lowest price a retailer is allowed to *advertise* a product for, as set by the manufacturer. Retailers can technically sell below MAP in-store, but cannot advertise below it online or in flyers. Violating MAP can result in the manufacturer cutting off supply.

**Example**: Apple sets a MAP of $999 for the iPhone 16. Best Buy can't advertise it for $949 on their website, even if they're willing to take the margin hit. They could offer a $50 gift card with purchase instead.

**In this solution**: The MAP guardrail (`check_map_compliance`) ensures no pricing scenario recommends a price below the manufacturer's MAP. Products in the `Products` DynamoDB table have an optional `mapPrice` field.

---
### MSRP — Manufacturer's Suggested Retail Price
**Definition**: The price a manufacturer recommends retailers charge consumers. Unlike MAP, MSRP is a suggestion, not a requirement. Retailers can price above or below MSRP.

**Example**: A Smart Watch has an MSRP of $299.99. Retailers can sell it for $279.99 (below MSRP to attract customers) or $319.99 (above MSRP if demand is high).

**In this solution**: Not explicitly implemented as a separate field, but the baseline prices in the Competitor API Server represent approximate MSRPs.

---

### P&L — Profit and Loss (Statement)
**Definition**: A financial statement summarizing revenues, costs, and expenses over a period. In pricing context, "P&L impact" means how a price change affects the company's profit.

**Example**: If you raise the price of Wireless Earbuds from $79.99 to $84.99 (+6.25%), and volume drops 3% due to elasticity, the net P&L impact is: (+6.25% price × 97% volume) = +3.1% revenue improvement.

**In this solution**: Each pricing scenario shows "projected P&L impact" — the estimated effect on revenue and margin if that scenario is implemented.

---

### SKU — Stock Keeping Unit
**Definition**: A unique identifier for each distinct product and variant. Every combination of product, size, color, and packaging gets its own SKU.

**Example**: "Organic Milk 1 Gallon" is one SKU. "Organic Milk Half Gallon" is a different SKU. They might be in the same product family but are priced independently.

**In this solution**: Product IDs like `ELEC-001`, `GROC-003`, `HOME-002` function as SKUs in the simulated product catalog.

---

### AOV — Average Order Value
**Definition**: The average dollar amount spent per transaction. Calculated as total revenue ÷ number of orders.

**Example**: If your store had $50,000 in revenue from 1,000 orders today, your AOV is $50.

**In this solution**: The ERP/POS MCP Server returns `averageBasketSize` and `averageTransactionValue` in POS real-time data, which the Demand Forecasting Agent uses to assess purchasing patterns.

---

### GM — Gross Margin
**Definition**: The percentage of revenue remaining after subtracting COGS. Formula: `(Revenue - COGS) / Revenue × 100`.

**Example**: Selling a product for $100 with COGS of $60 gives a gross margin of 40%. This means $0.40 of every dollar goes toward covering operating expenses and profit.

**In this solution**: `projectedMargin` in each pricing scenario represents the expected gross margin. The Cost & Finance MCP Server provides `margin_targets` by category and channel (e.g., electronics online target: 22%, apparel retail: 55%).

---
### pp — Percentage Points
**Definition**: The arithmetic difference between two percentages. Different from "percent change." If margin goes from 22% to 19%, that's a 3pp (percentage point) decline — NOT a 3% decline (which would be 22% × 0.97 = 21.34%).

**Example**: Risk classification uses pp for margin impact: ≤2pp = LOW risk, 2-5pp = MEDIUM, >5pp = HIGH. So if your margin drops from 25% to 22%, that's 3pp — MEDIUM risk.

**In this solution**: Margin variance threshold is 3pp (0.03 as a decimal). Risk classification thresholds use pp for margin impact assessment.

---

### STP — Straight-Through Processing
**Definition**: Automated end-to-end processing without human intervention. In pricing, it means a recommendation is automatically approved and implemented without requiring a human to click "approve."

**Example**: A 2% price increase on a commodity product (LOW risk) is auto-approved and pushed to all sales channels within 30 seconds — no human touches it.

**In this solution**: LOW risk scenarios (≤5% price change, ≤2pp margin impact) are auto-approved via `ApprovalActionType.AUTO_APPROVE` and immediately trigger the Implementation Monitoring Agent.

---

## Pricing Strategy Terms

### Price Elasticity of Demand
**Definition**: A measure of how sensitive customer demand is to price changes. Expressed as a negative number (price goes up → demand goes down). The more negative, the more sensitive.

**Formula**: `% change in quantity demanded ÷ % change in price`

**Examples**:
- Elasticity of **-0.5** (inelastic): A 10% price increase causes only a 5% drop in demand. Luxury goods, brand-loyal customers.
- Elasticity of **-1.3** (unit elastic): A 10% price increase causes a 13% drop in demand. Most mainstream retail products.
- Elasticity of **-2.1** (highly elastic): A 10% price increase causes a 21% drop in demand. Commodities, price-sensitive shoppers.

**In this solution**: The ERP/POS MCP Server returns elasticity coefficients for 5 customer segments. The Strategy Synthesis Agent uses these to project how demand will respond to each proposed price change.

---

### Cross-Price Elasticity
**Definition**: How demand for Product A changes when the price of Product B changes. Positive cross-elasticity means the products are substitutes (if B gets expensive, people buy A instead).

**Example**: If Coca-Cola raises prices 10% and Pepsi demand increases 5%, the cross-price elasticity is +0.5. They're substitutes.

**In this solution**: The ERP/POS MCP Server returns `crossPriceElasticity` per segment (range 0.1-0.8), indicating how much demand shifts when competitor prices change.

---

### Income Elasticity
**Definition**: How demand changes when consumer income changes. Positive means demand increases with income (normal goods). Negative means demand decreases with income (inferior goods).

**Example**: Organic food has income elasticity of +1.2 — as people earn more, they buy 20% more organic food for every 10% income increase.

**In this solution**: The ERP/POS MCP Server returns `incomeElasticity` per segment (range 0.3-1.5), used alongside macro indicators (disposable income change) to assess purchasing power.

---
### Price Index
**Definition**: A ratio comparing your price to the market average, expressed as a number where 100 = at market average. Below 100 means you're cheaper than average; above 100 means you're more expensive.

**Formula**: `(Your Price / Market Average Price) × 100`

**Example**: If the market average for Bluetooth Speakers is $145 and you price at $149.99, your price index is 103.4 — slightly premium.

**In this solution**: The Competitor API MCP Server calculates `priceIndex` and classifies positioning as "price_leader" (<95), "competitive" (95-105), or "premium" (>105).

---

### Composite Score
**Definition**: A single weighted number combining multiple metrics into one ranking value. Used to compare scenarios that have different strengths (one might be great for revenue but bad for margin).

**Formula in this solution**: `0.4 × projected_revenue + 0.35 × projected_margin + 0.25 × projected_market_share`

**Example**: Scenario A has high revenue but low margin (score: 850). Scenario B has moderate revenue and high margin (score: 920). Scenario B ranks higher because the weighted combination favors it.

**In this solution**: `calculate_composite_score()` in `shared/scenario_ranking.py` computes this for every scenario, then scenarios are sorted descending and assigned ranks 1 to N.

---

### Loss Leader
**Definition**: A product intentionally priced below cost (or at very low margin) to attract customers who will then buy other, profitable items. Common in grocery (e.g., cheap milk to get people in the store).

**Example**: A grocery store sells Organic Eggs at $4.99 (below the $7.49 cost) knowing that customers who come for eggs will also buy $50 of other groceries.

**In this solution**: The Cost & Finance MCP Server has a `max_loss_leader_items: 5` constraint — limiting how many products can be priced as loss leaders. The below-cost guardrail would normally reject these, but a production system would have an exception for designated loss leaders.

---

### Price War
**Definition**: A competitive situation where retailers repeatedly undercut each other's prices, driving margins toward zero. Usually triggered by one competitor making an aggressive price cut.

**Example**: Retailer A drops Wireless Earbuds to $69.99. Retailer B responds with $64.99. Retailer A goes to $59.99. Everyone loses margin.

**In this solution**: The Competitive Intelligence Agent detects price war signals by analyzing competitor price trends and volatility. If competitors are pricing aggressively (price index dropping, high volatility), the agent flags this as a risk factor that influences scenario generation.

---

### Seasonality Index
**Definition**: A multiplier indicating how much demand deviates from the annual average due to seasonal patterns. 1.0 = normal, >1.0 = peak season, <1.0 = off-season.

**Example**: Sunscreen has a seasonality index of 2.5 in summer (demand is 2.5× the annual average) and 0.3 in winter.

**In this solution**: The Market Signals MCP Server returns `seasonalityIndex` (range 0.5-1.5). The Demand Forecasting Agent uses this to adjust demand projections — higher seasonality supports more aggressive pricing.

---

## Regulatory & Compliance Terms

### FTC — Federal Trade Commission
**Definition**: The US government agency that enforces consumer protection and antitrust laws. Relevant to pricing because they prosecute deceptive pricing, predatory pricing, and price fixing.

**In this solution**: Bedrock Guardrails block strategies that would violate FTC regulations (predatory pricing, deceptive practices).

---
### Robinson-Patman Act
**Definition**: A US federal law (1936) that prohibits price discrimination — charging different prices to different buyers for the same product when it lessens competition. Exceptions exist for cost differences, meeting competition, and changing market conditions.

**Example**: A manufacturer can't sell the same widget to Retailer A for $10 and Retailer B for $15 unless there's a legitimate cost difference (e.g., Retailer A buys in larger quantities).

**In this solution**: The geographic bias guardrail (≤15% regional variance) prevents the system from recommending significantly different prices for the same product across regions, which could constitute Robinson-Patman violations.

---

### Sherman Act
**Definition**: The foundational US antitrust law (1890). Section 1 prohibits agreements that restrain trade (price fixing, market allocation). Section 2 prohibits monopolization and attempts to monopolize.

**Example**: If two competing retailers agree to both charge $99.99 for a product (instead of competing on price), that's a Section 1 violation — price fixing.

**In this solution**: Bedrock Guardrails block any request that implies price coordination with competitors (Section 1) or predatory pricing to eliminate competition (Section 2).

---

### EU Omnibus Directive
**Definition**: EU regulation (2019/2161) requiring retailers to show the lowest price from the previous 30 days when advertising a discount. Ensures price transparency and prevents fake "sales."

**Example**: If a product was $50 for the last 30 days and you raise it to $70 for one day, then "discount" it to $55, you must show the reference price as $50 (the lowest in 30 days), not $70.

**In this solution**: The audit trail in DynamoDB records every price change with timestamps, enabling compliance with the 30-day price history requirement. The Products table stores `previousPrice` and `priceUpdatedAt`.

---

### Colgate Doctrine
**Definition**: A legal principle (from *United States v. Colgate & Co.*, 1919) that allows manufacturers to unilaterally set minimum resale prices (MAP) and refuse to deal with retailers who don't comply — as long as there's no "agreement" to fix prices.

**Example**: Nike can say "our shoes must be advertised at $120 or above" and stop selling to any retailer who advertises below $120. This is legal because it's a unilateral policy, not a bilateral agreement.

**In this solution**: The MAP guardrail enforces these manufacturer policies automatically, ensuring the system never recommends advertising below the manufacturer's minimum.

---

### SOX — Sarbanes-Oxley Act
**Definition**: US law (2002) requiring publicly traded companies to maintain accurate financial records and internal controls. Relevant to pricing because pricing decisions affect revenue recognition and financial reporting.

**In this solution**: The full audit trail (DynamoDB AuditTrail table) provides the traceability required for SOX compliance — every pricing decision is recorded with who made it, when, and why.

---

### GDPR — General Data Protection Regulation
**Definition**: EU regulation governing the collection, processing, and storage of personal data. Relevant to pricing because customer purchase history and behavioral data used for personalized pricing must be handled carefully.

**In this solution**: The PII protection guardrail prevents customer-identifiable data (emails, phone numbers, account IDs, SSNs, credit cards) from appearing in agent communications or scenario outputs.

---

### CCPA — California Consumer Privacy Act
**Definition**: California state law giving consumers rights over their personal data, similar to GDPR. Relevant because personalized pricing based on consumer data must comply with disclosure requirements.

**In this solution**: Same PII protection guardrail applies. The system doesn't use individual customer data for pricing — it uses aggregate segment-level elasticity data.

---

## Macroeconomic Indicators

### CPI — Consumer Price Index
**Definition**: A measure of the average change in prices paid by consumers for a basket of goods and services over time. The primary measure of inflation.

**Example**: If CPI is 3.2%, prices are rising 3.2% per year on average. This affects how aggressively you can raise prices — consumers expect some inflation but resist price increases that exceed CPI.

**In this solution**: The Market Signals MCP Server returns CPI (range 1.5-4.5%). The Market Intelligence Agent uses this to assess whether price increases will be accepted by consumers.

---
### GDP — Gross Domestic Product
**Definition**: The total value of all goods and services produced in a country over a period. GDP growth indicates economic expansion; contraction indicates recession.

**Example**: GDP growth of 3% means the economy is expanding — consumers have more money to spend, supporting price increases. Negative GDP growth means recession — consumers cut spending.

**In this solution**: The Market Signals MCP Server returns `gdpGrowth` (range -1% to 5%). Positive GDP growth supports bullish pricing strategies.

---

### Consumer Confidence Index
**Definition**: A survey-based measure of how optimistic consumers feel about the economy and their personal finances. Higher confidence = more willingness to spend.

**Example**: Consumer Confidence of 120 (above baseline 100) means consumers feel good about the economy and are likely to make purchases. Below 80 means they're worried and cutting back.

**In this solution**: The Market Signals MCP Server returns `consumerConfidence` (range 70-130). The Market Intelligence Agent classifies the macro outlook as "bullish" (high confidence), "neutral", or "bearish" (low confidence).

---

## Retail Operations Terms

### POS — Point of Sale
**Definition**: The system where retail transactions are completed — the cash register, card terminal, or online checkout. POS data includes what was bought, when, how much, and payment method.

**Example**: POS data shows that Wireless Earbuds sell 45 units per hour on average, with peak sales between 6-8 PM, and average basket size of $85.

**In this solution**: The ERP/POS MCP Server's `get_pos_realtime` tool returns hourly transaction data including counts, units, revenue, basket sizes, and peak hours.

---

### ERP — Enterprise Resource Planning
**Definition**: A company's central business management system that integrates finance, supply chain, manufacturing, HR, and sales data. In retail, ERP holds inventory, purchase orders, cost data, and sales history.

**Example**: SAP, Oracle, or Microsoft Dynamics — the system that knows how much inventory you have, what it cost, and how fast it's selling.

**In this solution**: The ERP/POS MCP Server simulates ERP data access, providing sales history, inventory levels, and cost structures that a real ERP system would contain.

---

### MCP — Model Context Protocol
**Definition**: An open standard protocol that allows AI agents to access external tools and data sources in a standardized way. Think of it as a "USB port" for AI — any tool that speaks MCP can be plugged into any agent that supports MCP.

**Example**: Instead of hardcoding API calls into each agent, you expose your ERP data as an MCP Server. Any agent can then call `get_sales_history` or `get_inventory_levels` without knowing the underlying implementation.

**In this solution**: 4 Lambda functions implement the MCP protocol, each exposing domain-specific tools. Agents connect to them via the Strands SDK's `MCPClient`.

---

### HITL — Human-in-the-Loop
**Definition**: A design pattern where AI systems include human decision points for high-stakes or uncertain situations. The AI does the analysis, but a human makes the final call on important decisions.

**Example**: The AI generates 50 pricing scenarios and recommends the top 3. For a 20% price increase (HIGH risk), a human Product Manager must review and approve before it goes live.

**In this solution**: Risk-based approval routing implements HITL — LOW risk is automated, MEDIUM requires human review, HIGH requires human review with written justification.

---
### Channel (Sales Channel)
**Definition**: A distinct path through which products reach customers. Each channel may have different pricing rules, margins, and competitive dynamics.

**Common channels**:
- **Online** (your website): Full control, dynamic pricing possible, lower overhead
- **Retail Store** (physical): Price match guarantees, no dynamic pricing, higher overhead
- **Marketplace** (Amazon, eBay): Platform fees (12%), limited pricing control, high competition
- **Wholesale** (B2B): Volume discounts, lower margins, long-term contracts

**In this solution**: The Cost & Finance MCP Server returns channel-specific rules (max discounts, fees, dynamic pricing enabled/disabled). Products have a `channels` field listing which channels they're sold through.

---

### Conversion Rate
**Definition**: The percentage of visitors/shoppers who actually make a purchase. A key metric for evaluating whether a price change is helping or hurting sales.

**Formula**: `Number of purchases ÷ Number of visitors × 100`

**Example**: If 1,000 people visit your product page and 35 buy, your conversion rate is 3.5%. If you raise the price and conversion drops to 2.8%, you're losing customers.

**In this solution**: The Implementation Monitoring Agent tracks `actual_conversion_rate` vs `projected_conversion_rate` as part of post-implementation KPI monitoring.

---

### Days of Supply
**Definition**: How many days your current inventory will last at the current sales rate. Low days of supply = risk of stockout. High days of supply = risk of overstock.

**Formula**: `Current inventory ÷ Average daily sales`

**Example**: 5,000 units in warehouse, selling 200/day = 25 days of supply. If it takes 14 days to reorder, you need to reorder when you hit 14 days of supply.

**In this solution**: The ERP/POS MCP Server returns `daysOfSupply` per location (warehouses ~30 days, stores ~14 days). Low days of supply might trigger more aggressive pricing to slow demand, while high days of supply might trigger discounts to move inventory.

---

### Reorder Point
**Definition**: The inventory level at which a new purchase order should be placed to avoid stockout. Accounts for lead time and safety stock.

**Example**: If it takes 7 days to receive new stock and you sell 100 units/day, your reorder point is 700 units (plus safety stock).

**In this solution**: The ERP/POS MCP Server returns `reorderPoint` per location. The Demand Forecasting Agent considers this when assessing supply constraints that affect pricing flexibility.

---

## AI/ML Terms Used in This Solution

### AgentCore
**Definition**: Amazon Bedrock AgentCore — a managed service providing Runtime (execution), Gateway (tool routing), Memory (state persistence), Browser (web scraping), Identity (credentials), and Observability (tracing) for AI agents.

**In this solution**: All 6 agents are deployed on AgentCore Runtime. MCP Servers are registered as Gateway targets. Memory stores historical outcomes.

---

### Strands Agents SDK
**Definition**: An open-source Python SDK for building AI agents that can use tools, maintain context, and be deployed on Amazon Bedrock AgentCore. Provides the `Agent` class, `@tool` decorator, and `MCPClient` for tool integration.

**In this solution**: Every agent is created using `Agent(model=..., system_prompt=..., tools=[...])` from the Strands SDK.

---
### SigV4 — Signature Version 4
**Definition**: AWS's request signing protocol that authenticates API calls. Every request to AWS services includes a cryptographic signature proving the caller's identity. Required for AgentCore Runtime API calls from Lambda.

**In this solution**: Lambda handlers use SigV4 HTTP calls (not boto3) to invoke AgentCore Runtime because the Lambda-bundled boto3 doesn't include the `bedrock-agentcore` service client.

---

### ULID — Universally Unique Lexicographically Sortable Identifier
**Definition**: A 128-bit identifier that is globally unique AND sortable by creation time. Better than UUID for database keys because records naturally sort chronologically.

**In this solution**: Pricing cycle IDs and scenario IDs use ULID format, ensuring they sort by creation time in DynamoDB queries.

---

### TTL — Time to Live
**Definition**: An expiration mechanism where records are automatically deleted after a specified time. Used to clean up stale data without manual intervention.

**In this solution**: DynamoDB PricingCycles table has a `ttl` attribute. Stuck cycles (status never reaches COMPLETE) auto-expire after 1 hour. Completed cycles have their TTL removed so they persist indefinitely.

---

### CDN — Content Delivery Network
**Definition**: A globally distributed network of servers that caches and delivers content (web pages, images, scripts) from the location closest to the user, reducing latency.

**In this solution**: CloudFront CDN delivers the Dashboard and Storefront React apps from edge locations worldwide, ensuring fast page loads regardless of user location.

---

### IaC — Infrastructure as Code
**Definition**: Managing and provisioning infrastructure through code files rather than manual console clicks. Enables version control, reproducibility, and automated deployment.

**In this solution**: AWS CDK (Python) defines all infrastructure — DynamoDB tables, Lambda functions, API Gateway, Cognito, CloudFront, S3 buckets. Running `cdk deploy` provisions everything automatically.

---

## Pricing Scenario Classification Terms

### Risk Level
**Definition**: A classification of how "risky" a pricing recommendation is, based on the magnitude of change and potential business impact.

| Level | Criteria | What It Means |
|-------|----------|---------------|
| LOW | ≤5% price change AND ≤2pp margin impact | Safe, routine adjustment. Auto-approved. |
| MEDIUM | 5-15% price change OR 2-5pp margin impact | Significant change. Needs human review. |
| HIGH | >15% price change OR >5pp margin OR >20% deviation from 90-day avg | Major change. Requires justification. |

---

### Confidence Score
**Definition**: An integer from 0 to 100 representing how likely the projected business impact will actually be realized. Higher = more confident in the prediction.

**How it's calculated**:
- Base confidence by risk level: LOW=80, MEDIUM=55, HIGH=30
- +5 bonus for each intelligence agent that provided data (max +15)
- ±5 random adjustment for differentiation
- Clamped to [0, 100]

**Example**: A LOW risk scenario with all 3 intelligence agents contributing gets: 80 + 15 ± 5 = 90-100 confidence. A HIGH risk scenario missing one agent's data gets: 30 + 10 ± 5 = 35-45 confidence.

---

### Status Label
**Definition**: A human-readable label on each scenario indicating what action is needed.

| Label | Meaning | Action Required |
|-------|---------|-----------------|
| "Recommended" | LOW risk, all guardrails passed | Auto-approved, no human action needed |
| "Review Required" | MEDIUM risk, needs human judgment | Product Manager reviews and approves/rejects |
| "Human Exception Handling" | HIGH risk, significant change | Product Manager must provide ≥50 character written justification |

---

## Summary Quick Reference Table

| Abbreviation | Full Form | One-Line Definition |
|-------------|-----------|-------------------|
| COGS | Cost of Goods Sold | Direct cost to produce/purchase a product |
| MAP | Minimum Advertised Price | Lowest price a manufacturer allows you to advertise |
| MSRP | Manufacturer's Suggested Retail Price | Recommended selling price (not mandatory) |
| P&L | Profit and Loss | Financial impact on revenue and profit |
| SKU | Stock Keeping Unit | Unique product identifier |
| AOV | Average Order Value | Average spend per transaction |
| GM | Gross Margin | Revenue minus COGS as a percentage |
| pp | Percentage Points | Arithmetic difference between two percentages |
| STP | Straight-Through Processing | Fully automated approval without human intervention |
| POS | Point of Sale | Where transactions happen (register/checkout) |
| ERP | Enterprise Resource Planning | Central business management system |
| MCP | Model Context Protocol | Standard protocol for AI agent tool access |
| HITL | Human-in-the-Loop | Human decision point in an AI workflow |
| CPI | Consumer Price Index | Measure of inflation |
| GDP | Gross Domestic Product | Total economic output of a country |
| FTC | Federal Trade Commission | US consumer protection/antitrust agency |
| SOX | Sarbanes-Oxley Act | US financial reporting compliance law |
| GDPR | General Data Protection Regulation | EU data privacy law |
| CCPA | California Consumer Privacy Act | California data privacy law |
| SigV4 | Signature Version 4 | AWS request authentication protocol |
| ULID | Universally Unique Lexicographically Sortable ID | Time-sortable unique identifier |
| TTL | Time to Live | Auto-expiration for database records |
| CDN | Content Delivery Network | Global content caching for fast delivery |
| IaC | Infrastructure as Code | Managing infrastructure via code files |
| CDK | Cloud Development Kit | AWS IaC framework (Python/TypeScript) |
| IAM | Identity and Access Management | AWS permissions and roles system |
| JWT | JSON Web Token | Compact token for authentication |
| CORS | Cross-Origin Resource Sharing | Browser security policy for API access |
| RBAC | Role-Based Access Control | Permissions based on user roles |
| KPI | Key Performance Indicator | Metric used to evaluate success |
| DR | Disaster Recovery | Plan for recovering from system failures |
