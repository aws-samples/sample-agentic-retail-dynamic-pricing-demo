# Implementation Plan: Retail Dynamic Pricing

## Overview

This plan implements an MVP demo of an agentic AI-based dynamic pricing system for retail. The build order follows a bottom-up approach: infrastructure first, then data layer, MCP servers, individual agents (tested in isolation), orchestrator, API layer, and finally both frontend applications. Each agent is tested individually via InvokeAgentRuntime before wiring the full pipeline.

Key technical constraints:
- SigV4 HTTP calls for AgentCore (not boto3)
- CORS: no allowCredentials with wildcard origins
- Lambda bundled boto3 doesn't have bedrock-agentcore — use SigV4 HTTP
- Each agent tested individually before orchestrator integration

## Tasks

- [x] 1. Project scaffolding and CDK infrastructure
  - [x] 1.1 Initialize project structure and CDK app
    - Create monorepo directory structure: `cdk/`, `backend/`, `frontend/dashboard/`, `frontend/storefront/`, `shared/`
    - Initialize CDK app with Python (`cdk init app --language python`)
    - Set up `pyproject.toml` with dependencies (aws-cdk-lib, constructs, strands-agents, hypothesis)
    - _Requirements: 11.1_

  - [x] 1.2 Define DynamoDB tables in CDK
    - Create `PricingCycles` table (PK: cycleId, SK: status, on-demand billing)
    - Create `PricingScenarios` table (PK: cycleId, SK: scenarioId, on-demand billing)
    - Create `Products` table (PK: productId, on-demand billing)
    - Create `AuditTrail` table (PK: scenarioId, SK: timestamp#ruleId, on-demand billing)
    - Create `Approvals` table (PK: scenarioId, SK: timestamp, on-demand billing)
    - _Requirements: 11.2_

  - [x] 1.3 Define Cognito User Pool and App Client in CDK
    - Create Cognito User Pool with email sign-in
    - Create App Client for Dashboard authentication
    - Configure JWT token settings for API Gateway integration
    - _Requirements: 11.3_

  - [x] 1.4 Define API Gateway REST API in CDK
    - Create REST API with Cognito authorizer for protected endpoints
    - Define all 8 endpoints (POST /pricing-cycles, GET /pricing-cycles/{id}, GET /pricing-cycles/{id}/scenarios, POST /approvals, GET /agents/status, GET /monitoring/{scenarioId}, GET /products, GET /products/{id})
    - Configure CORS with specific origins (no wildcard with credentials)
    - Set up Lambda integrations for each endpoint
    - _Requirements: 11.5, 11.6_

  - [x] 1.5 Define Lambda functions for MCP Servers in CDK
    - Create 4 Lambda function constructs (Competitor API, ERP/POS, Market Signals, Cost & Finance)
    - Configure Python 3.12 runtime, 256 MB memory, 30s timeout
    - Set up IAM roles with least-privilege permissions
    - _Requirements: 2.5, 11.1_

  - [x] 1.6 Define CloudFront and Amplify hosting in CDK
    - Create CloudFront distribution for Dashboard and Storefront
    - Configure Amplify hosting for both frontend apps
    - Set up custom domain routing (if applicable)
    - _Requirements: 11.4, 4.8, 6.4_

  - [x] 1.7 Define API Gateway Lambda integrations in CDK
    - Create Lambda functions for API endpoint handlers
    - Wire Lambda functions to API Gateway routes
    - Configure SigV4 signing for AgentCore invocations from Lambda handlers
    - _Requirements: 11.5, 11.7_

- [x] 2. Checkpoint - Verify CDK synthesizes successfully
  - Run `cdk synth` and ensure all stacks synthesize without errors. Ask the user if questions arise.

- [x] 3. Data models and shared utilities
  - [x] 3.1 Create Pricing Scenario data model and JSON schema
    - Define Python dataclass/Pydantic model for PricingScenario with all fields from design
    - Implement JSON serialization preserving 4 decimal places for monetary values
    - Implement JSON deserialization with schema validation (required fields, type checking)
    - Create shared schema definition matching the JSON Schema in design document
    - _Requirements: 14.1, 14.2, 14.4_

  - [x] 3.2 Implement guardrails engine as pure functions
    - Implement below-cost rejection: `price >= total_unit_cost`
    - Implement MAP enforcement: `price >= minimum_advertised_price`
    - Implement geographic bias detection: `max_regional_variance <= threshold%`
    - Implement PII protection check for agent communications
    - Return structured guardrail results with rule name, pass/fail, and reason
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 3.3 Implement risk classification function
    - Classify LOW: price change ≤5% AND margin impact ≤2pp
    - Classify MEDIUM: price change 5-15% OR margin impact 2-5pp
    - Classify HIGH: price change >15% OR margin impact >5pp OR >20% deviation from 90-day avg
    - Map risk level to status label (Recommended, Review Required, Human Exception Handling)
    - _Requirements: 7.4, 3.7_

  - [x] 3.4 Implement approval routing function
    - Auto-approve for LOW risk within 30 seconds
    - Route to Product Manager for MEDIUM risk
    - Route as exception for HIGH risk (require ≥50 char justification)
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 3.5 Implement scenario ranking function
    - Calculate composite business impact score from revenue, margin, and market share
    - Sort scenarios by composite score descending
    - Assign contiguous ranks from 1 to N
    - _Requirements: 3.2_

  - [x] 3.6 Implement variance detection function
    - Compare actual vs. projected revenue (threshold: 10%)
    - Compare actual vs. projected margin (threshold: 3 percentage points)
    - Return adjustment recommendation when thresholds breached
    - _Requirements: 9.3_

  - [x] 3.7 Write property tests for guardrails engine
    - **Property 11: Below-cost guardrail rejects correctly**
    - **Property 12: MAP guardrail rejects correctly**
    - **Property 13: Geographic bias guardrail flags correctly**
    - **Validates: Requirements 8.1, 8.2, 8.3**

  - [x] 3.8 Write property tests for risk classification
    - **Property 9: Risk classification follows threshold rules**
    - **Validates: Requirements 7.4**

  - [x] 3.9 Write property tests for scenario ranking
    - **Property 1: Scenario ranking is contiguous and ordered by composite score**
    - **Validates: Requirements 1.3, 3.2**

  - [x] 3.10 Write property tests for serialization round trip
    - **Property 15: Pricing Scenario serialization round trip**
    - **Property 16: Schema validation rejects invalid payloads**
    - **Validates: Requirements 14.5, 14.2, 14.3**

  - [x] 3.11 Write property tests for confidence scores and scenario count
    - **Property 5: Confidence scores are valid integers**
    - **Property 4: Scenario count within bounds**
    - **Validates: Requirements 3.3, 3.1, 3.6**

- [x] 4. Checkpoint - Verify data models and business logic
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. MCP Servers (Lambda functions with randomized demo data)
  - [x] 5.1 Implement Competitor API MCP Server
    - Create Lambda handler with MCP tool definitions: `get_competitor_prices`, `get_price_history`, `get_market_position`
    - Implement randomized data generation within ±10% variance from baseline
    - Return JSON response with `status` and `data` fields conforming to MCP Response Schema
    - Include `metadata` with timestamp, source, and latencyMs
    - _Requirements: 2.1, 2.5, 2.6_

  - [x] 5.2 Implement ERP/POS MCP Server
    - Create Lambda handler with MCP tool definitions: `get_sales_history`, `get_pos_realtime`, `get_inventory_levels`, `get_elasticity_data`
    - Implement randomized data generation within ±20% variance for demand volumes
    - Return JSON response conforming to MCP Response Schema
    - _Requirements: 2.2, 2.5, 2.6_

  - [x] 5.3 Implement Market Signals MCP Server
    - Create Lambda handler with MCP tool definitions: `get_market_trends`, `get_consumer_sentiment`, `get_macro_indicators`
    - Implement randomized sentiment scores varying between invocations
    - Return JSON response conforming to MCP Response Schema
    - _Requirements: 2.3, 2.5, 2.6_

  - [x] 5.4 Implement Cost & Finance MCP Server
    - Create Lambda handler with MCP tool definitions: `get_cost_structure`, `get_margin_targets`, `get_financial_constraints`
    - Implement randomized cost inputs within ±5% variance from baseline
    - Return JSON response conforming to MCP Response Schema
    - _Requirements: 2.4, 2.5, 2.6_

  - [x] 5.5 Write property tests for MCP Server responses
    - **Property 2: MCP Server responses conform to schema**
    - **Property 3: MCP Server data within variance bounds**
    - **Validates: Requirements 2.5, 2.6**

  - [x] 5.6 Write integration tests for MCP Servers
    - Test each MCP Server with at least 2 known inputs (nominal + error case)
    - Validate response schema conformance
    - _Requirements: 12.3_

- [x] 6. Checkpoint - Verify MCP Servers
  - Deploy MCP Server Lambda functions and verify each returns valid responses. Ensure all tests pass, ask the user if questions arise.

- [x] 7. Individual agents (Strands Agents SDK on AgentCore)
  - [x] 7.1 Implement Competitive Intelligence Agent
    - Define agent with Strands SDK using model `us.anthropic.claude-sonnet-4-6`
    - Configure MCP client connection to Competitor API Server
    - Write system prompt for competitive analysis (channel-level analysis, sentiment detection)
    - Define structured output schema for competitive factors
    - Implement AgentCore Browser fallback logic (use MCP when Browser unavailable)
    - _Requirements: 1.7, 2.1, 2.10_

  - [x] 7.2 Implement Demand Forecasting Agent
    - Define agent with Strands SDK using model `us.anthropic.claude-sonnet-4-6`
    - Configure MCP client connection to ERP/POS Server
    - Write system prompt for demand analysis (sales history, POS data, inventory, elasticity)
    - Define structured output schema for demand factors
    - _Requirements: 1.7, 2.2_

  - [x] 7.3 Implement Market Intelligence Agent
    - Define agent with Strands SDK using model `us.anthropic.claude-sonnet-4-6`
    - Configure MCP client connection to Market Signals Server
    - Write system prompt for market analysis (cross-product, market structure, opportunity detection)
    - Define structured output schema for market factors
    - _Requirements: 1.7, 2.3_

  - [x] 7.4 Implement Strategy Synthesis Agent
    - Define agent with Strands SDK using model `us.anthropic.claude-opus-4-7`
    - Configure MCP client connection to Cost & Finance Server
    - Write system prompt for strategy synthesis (combine inputs, apply guardrails, generate 50-200 scenarios)
    - Integrate guardrails engine for scenario validation
    - Implement scenario ranking by composite business impact score
    - Assign confidence scores (0-100) and status labels based on risk classification
    - _Requirements: 1.6, 3.1, 3.2, 3.3, 3.4, 3.5, 3.7_

  - [x] 7.5 Implement Implementation Monitoring Agent
    - Define agent with Strands SDK using model `us.anthropic.claude-sonnet-4-6`
    - Implement price update execution across sales channels
    - Implement KPI tracking (revenue, conversion rate, margin vs. projected)
    - Implement variance detection and adjustment recommendation generation
    - _Requirements: 1.4, 9.1, 9.2, 9.3, 9.4_

  - [x] 7.6 Create SigV4 HTTP utility for AgentCore invocations
    - Implement SigV4 request signing for Bedrock AgentCore Runtime API
    - Create helper function for InvokeAgentRuntime calls
    - Handle response streaming and error cases
    - _Requirements: 11.7_

  - [x] 7.7 Create agent testing harness for individual invocation
    - Write test script to invoke each agent individually via InvokeAgentRuntime (SigV4)
    - Include sample request payloads and expected response schemas per agent
    - Validate response conforms to agent's defined output schema within 30 seconds
    - Document testing guide with sample payloads
    - _Requirements: 12.1, 12.2, 12.4_

  - [x] 7.8 Write property tests for Strategy Synthesis Agent output
    - **Property 6: Guardrail-violating scenarios excluded from output**
    - **Property 7: Each scenario references all three intelligence agents**
    - **Property 8: Status label matches risk classification**
    - **Validates: Requirements 3.4, 3.5, 3.7, 8.6**

  - [x] 7.9 Write property tests for approval routing
    - **Property 10: Approval routing matches risk level**
    - **Validates: Requirements 7.1, 7.2, 7.3**

  - [x] 7.10 Write property tests for variance detection
    - **Property 14: Variance detection triggers adjustment correctly**
    - **Validates: Requirements 9.3**

- [x] 8. Checkpoint - Verify individual agents
  - Test each agent individually via InvokeAgentRuntime. Ensure all agents return valid responses within 30 seconds. Ask the user if questions arise.

- [x] 9. Orchestrator agent (wire the pipeline)
  - [x] 9.1 Implement Orchestrator Agent
    - Define orchestrator with Strands SDK using model `us.anthropic.claude-opus-4-7`
    - Write system prompt for orchestration (delegate, coordinate, assemble)
    - Implement parallel invocation of 3 intelligence agents
    - Implement sequential handoff to Strategy Synthesis Agent after parallel phase completes
    - Implement handoff to Implementation Monitoring Agent after approval
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 9.2 Implement session management and data isolation
    - Create AgentCore session scoped to Pricing_Group level
    - Enforce data isolation between concurrent sessions
    - Configure short-term memory (24h TTL) for session-bound data
    - Configure long-term memory (100 cycles) for historical learning via AgentCore Memory
    - _Requirements: 1.9, 1.10, 10.1, 10.2, 10.4_

  - [x] 9.3 Implement timeout, retry, and graceful degradation logic
    - Enforce 120-second timeout per sub-agent
    - Implement retry up to 2 times per failed agent
    - Implement graceful degradation (proceed with available outputs, flag incomplete)
    - Handle MCP Server timeout (30s) with single retry after 2s wait
    - _Requirements: 1.5, 1.8, 2.7, 2.8, 2.9_

  - [x] 9.4 Implement DynamoDB persistence for pricing cycles
    - Write pricing cycle initiation to PricingCycles table
    - Update agent statuses during execution
    - Store generated scenarios to PricingScenarios table
    - Write guardrail audit trail to AuditTrail table
    - _Requirements: 8.5, 11.2_

  - [x] 9.5 Implement observability and logging
    - Log all agent interactions to CloudWatch (timestamp, agentId, action, input/output summary, duration)
    - Integrate AgentCore Observability for end-to-end trace correlation
    - Emit CloudWatch metrics on agent errors (agent identifier + error category)
    - Configure CloudWatch alarm for error rate threshold (5 errors per 1-minute window)
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

  - [x] 9.6 Implement historical memory query for scenario generation
    - Query long-term memory for past outcomes of same product/category
    - Pass historical data to Strategy Synthesis Agent context
    - Persist approved scenario outcomes to long-term memory within 60 seconds
    - _Requirements: 10.3, 10.5_

- [x] 10. Checkpoint - Verify orchestrator end-to-end
  - Run a full pricing cycle through the orchestrator. Verify parallel agent execution, scenario generation, and DynamoDB persistence. Ensure all tests pass, ask the user if questions arise.

- [x] 11. API Gateway Lambda handlers
  - [x] 11.1 Implement POST /pricing-cycles handler
    - Parse request body (pricingGroup, objectives, constraints)
    - Validate required fields
    - Invoke Orchestrator Agent via SigV4 HTTP
    - Return cycleId and initial status
    - _Requirements: 4.9, 1.1_

  - [x] 11.2 Implement GET /pricing-cycles/{id} and GET /pricing-cycles/{id}/scenarios handlers
    - Query PricingCycles table for cycle status and agent statuses
    - Query PricingScenarios table for scenarios (paginated, 20/page, sorted by rank)
    - Return structured response with cycle metadata and scenario list
    - _Requirements: 4.1, 4.2_

  - [x] 11.3 Implement POST /approvals handler
    - Parse approval action (approve/reject), comment, and scenario ID
    - Validate HIGH risk requires ≥50 character justification
    - Write approval record to Approvals table
    - Update scenario approvalStatus in PricingScenarios table
    - Trigger Implementation Monitoring Agent on approval
    - Update product prices in Products table on approval
    - _Requirements: 4.3, 7.1, 7.2, 7.3, 7.5_

  - [x] 11.4 Implement GET /agents/status and GET /monitoring/{scenarioId} handlers
    - Return real-time agent execution status from PricingCycles table
    - Return monitoring metrics (actual vs. projected) for approved scenarios
    - _Requirements: 4.1, 9.6_

  - [x] 11.5 Implement GET /products and GET /products/{id} handlers (public)
    - Query Products table for full catalog or single product
    - No authentication required (storefront endpoints)
    - Include price change indicator for products updated in last 24 hours
    - _Requirements: 6.1, 6.2, 6.5_

  - [x] 11.6 Seed Products table with demo data
    - Create seed script to populate Products table with sample retail products
    - Include varied categories, sub-categories, product families
    - Set baseline prices, costs, MAP prices, channels, and regions
    - _Requirements: 6.1_

- [x] 12. Checkpoint - Verify API endpoints
  - Test all API Gateway endpoints with sample requests. Verify Cognito auth on protected endpoints and public access on storefront endpoints. Ensure all tests pass, ask the user if questions arise.

- [ ] 13. Dashboard frontend application
  - [x] 13.1 Initialize Dashboard app with Vite, React, TypeScript, Tailwind CSS
    - Scaffold Vite + React + TypeScript project in `frontend/dashboard/`
    - Configure Tailwind CSS
    - Set up Axios instance with base URL and Cognito JWT interceptor
    - Configure environment variables for API Gateway URL and Cognito settings
    - _Requirements: 4.5_

  - [ ] 13.2 Implement Cognito authentication flow
    - Integrate Amazon Cognito Hosted UI or Amplify Auth library
    - Implement login/logout flow with JWT token management
    - Redirect to login on auth failure with error message
    - Protect all Dashboard routes with auth guard
    - _Requirements: 4.6, 4.7_

  - [ ] 13.3 Implement Pricing Request Form
    - Build form with Pricing Group dropdown (product family, sub-category, category)
    - Add strategic objectives multi-select (revenue maximization, margin protection, market share growth, competitive positioning)
    - Add business constraints inputs (min margin %, max price change %, channel restrictions)
    - Validate all required fields before submission
    - Submit to POST /pricing-cycles endpoint
    - _Requirements: 4.9, 5.1_

  - [ ] 13.4 Implement Agent Status Panel
    - Display status of each agent (idle, running, completed, failed)
    - Poll GET /agents/status every 5 seconds
    - Show step-by-step visual flow with agent names and execution order
    - Display progress indicators and intermediate results
    - _Requirements: 4.1, 5.2, 5.3_

  - [ ] 13.5 Implement Scenario List and Detail View
    - Display paginated scenario list (20/page) sorted by rank
    - Show rank, confidence score, status label, projected P&L impact per scenario
    - Display top 3 scenarios with contributing factors breakdown
    - Show data sources consulted and confidence score rationale
    - _Requirements: 4.2, 5.4_

  - [ ] 13.6 Implement Approval Workflow UI
    - Add approve/reject/modify buttons per scenario
    - Require free-text comment on all actions
    - Enforce ≥50 character justification for HIGH risk approvals
    - Show confirmation indicator within 2 seconds of submission
    - Display rejection reason and scenario status updates
    - _Requirements: 4.3, 7.3, 7.6_

  - [ ] 13.7 Implement AI Sidebar (rationale and process flow)
    - Display AI rationale for recommendations
    - Show visual process flow of agent interactions
    - Display agent interaction logs with timing data (millisecond precision)
    - Show at least 100 most recent log entries per Pricing Cycle
    - _Requirements: 4.4, 13.5_

  - [ ] 13.8 Implement Continuous Monitoring Panel
    - Display actual vs. projected performance for active implementations
    - Show trend visualization charts
    - Display variance alerts and recommended corrective actions
    - Allow approval of corrective actions
    - _Requirements: 9.6, 9.4, 9.5_

  - [ ] 13.9 Implement demo flow error handling
    - Display error indication for failed/timed-out agents
    - Allow restart of demo from beginning on failure
    - Handle API timeout with retry button
    - _Requirements: 5.5, 4.7_

- [ ] 14. Checkpoint - Verify Dashboard
  - Build Dashboard app successfully. Verify all views render correctly with mock data. Ensure Cognito auth flow works. Ask the user if questions arise.

- [ ] 15. Storefront frontend application
  - [x] 15.1 Initialize Storefront app with Vite, React, TypeScript, Tailwind CSS
    - Scaffold Vite + React + TypeScript project in `frontend/storefront/`
    - Configure Tailwind CSS
    - Set up Axios instance with base URL (no auth)
    - Configure environment variables for API Gateway URL
    - _Requirements: 6.4_

  - [ ] 15.2 Implement Product Catalog page
    - Display product grid with image, description, and pricing
    - Fetch products from GET /products endpoint
    - Show visual change indicator for prices updated in last 24 hours
    - Implement auto-retry on data fetch failure (10 second interval)
    - Display "temporarily unavailable" message on persistent failure
    - _Requirements: 6.1, 6.2, 6.3, 6.5, 6.6_

  - [ ] 15.3 Implement Product Detail page
    - Display single product with full details
    - Fetch from GET /products/{id} endpoint
    - Show price history and change indicator
    - _Requirements: 6.5_

- [ ] 16. Checkpoint - Verify Storefront
  - Build Storefront app successfully. Verify product catalog renders with demo data. Ensure no authentication is required. Ask the user if questions arise.

- [ ] 17. Integration testing and demo flow
  - [ ] 17.1 Write end-to-end integration test for pricing cycle
    - Test full flow: submit request → agents execute → scenarios generated → approval → price update
    - Verify DynamoDB records at each stage
    - Verify Storefront price update within 60 seconds of approval
    - _Requirements: 1.1, 6.2_

  - [ ] 17.2 Write escalation and timeout handling tests
    - Test 48-hour escalation deadline logic
    - Test agent timeout and retry behavior
    - Test graceful degradation with partial agent failures
    - _Requirements: 7.7, 1.5, 1.8_

  - [ ] 17.3 Verify CDK deployment end-to-end
    - Run `cdk deploy` and verify all resources provisioned
    - Verify automatic rollback on failure
    - _Requirements: 11.1, 11.8_

- [ ] 18. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- SigV4 HTTP calls are required for all AgentCore interactions (Lambda bundled boto3 lacks bedrock-agentcore)
- CORS must use specific origins (not wildcard) when credentials are involved
- Test each agent individually before wiring the orchestrator pipeline
- MCP Servers return randomized data to demonstrate adaptive agent behavior across demo runs

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.5", "1.6"] },
    { "id": 2, "tasks": ["1.4", "1.7", "3.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "3.4", "3.5", "3.6"] },
    { "id": 4, "tasks": ["3.7", "3.8", "3.9", "3.10", "3.11", "5.1", "5.2", "5.3", "5.4"] },
    { "id": 5, "tasks": ["5.5", "5.6", "7.6"] },
    { "id": 6, "tasks": ["7.1", "7.2", "7.3", "7.4", "7.5"] },
    { "id": 7, "tasks": ["7.7", "7.8", "7.9", "7.10"] },
    { "id": 8, "tasks": ["9.1"] },
    { "id": 9, "tasks": ["9.2", "9.3", "9.4", "9.5", "9.6"] },
    { "id": 10, "tasks": ["11.1", "11.2", "11.3", "11.4", "11.5", "11.6"] },
    { "id": 11, "tasks": ["13.1", "15.1"] },
    { "id": 12, "tasks": ["13.2", "15.2"] },
    { "id": 13, "tasks": ["13.3", "13.4", "13.5", "13.6", "13.7", "13.8", "13.9", "15.3"] },
    { "id": 14, "tasks": ["17.1", "17.2", "17.3"] }
  ]
}
```
