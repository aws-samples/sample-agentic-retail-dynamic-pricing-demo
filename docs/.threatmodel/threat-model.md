# Comprehensive Threat Model Report

**Generated**: 2026-07-01 16:26:37
**Current Phase**: 1 - Business Context Analysis
**Overall Completion**: 80.0%

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Business Context](#business-context)
3. [System Architecture](#system-architecture)
4. [Threat Actors](#threat-actors)
5. [Trust Boundaries](#trust-boundaries)
6. [Assets and Flows](#assets-and-flows)
7. [Threats](#threats)
8. [Mitigations](#mitigations)
9. [Assumptions](#assumptions)
10. [Phase Progress](#phase-progress)

## Executive Summary

Retail Dynamic Pricing is an agentic AI system that transforms retail pricing from a manual 6-10 week process into an autonomous workflow completing in under 2 minutes. Built on Amazon Bedrock AgentCore with 6 specialized AI agents that gather market intelligence, analyze demand, and generate optimized pricing recommendations with human-in-the-loop approval. The system enforces compliance via Amazon Bedrock Guardrails (blocks predatory pricing, price fixing, discrimination, gouging), routes approvals by risk level (LOW auto-approved, MEDIUM/HIGH routed to humans), and provides full audit trail for regulatory compliance (FTC, Robinson-Patman Act, EU Omnibus Directive). It serves both Pricing Analysts (who run pricing cycles and approve scenarios) and Operations teams (who monitor system health and metrics).

### Key Statistics

- **Total Threats**: 12
- **Total Mitigations**: 12
- **Total Assumptions**: 8
- **System Components**: 29
- **Assets**: 16
- **Threat Actors**: 17

## Business Context

**Description**: Retail Dynamic Pricing is an agentic AI system that transforms retail pricing from a manual 6-10 week process into an autonomous workflow completing in under 2 minutes. Built on Amazon Bedrock AgentCore with 6 specialized AI agents that gather market intelligence, analyze demand, and generate optimized pricing recommendations with human-in-the-loop approval. The system enforces compliance via Amazon Bedrock Guardrails (blocks predatory pricing, price fixing, discrimination, gouging), routes approvals by risk level (LOW auto-approved, MEDIUM/HIGH routed to humans), and provides full audit trail for regulatory compliance (FTC, Robinson-Patman Act, EU Omnibus Directive). It serves both Pricing Analysts (who run pricing cycles and approve scenarios) and Operations teams (who monitor system health and metrics).

### Business Features

- **Industry Sector**: Retail
- **Data Sensitivity**: Confidential
- **User Base Size**: Medium
- **Geographic Scope**: Multinational
- **Regulatory Requirements**: Multiple
- **System Criticality**: High
- **Financial Impact**: High
- **Authentication Requirement**: MFA
- **Deployment Environment**: Cloud-Public
- **Integration Complexity**: Complex

## System Architecture

### Components

| ID | Name | Type | Service Provider | Description |
|---|---|---|---|---|
| C001 | CloudFront Dashboard Distribution | Network | AWS | CDN distribution serving the authenticated Pricing Analyst dashboard (React/TS). Redirects HTTP to HTTPS, caches static assets. |
| C002 | CloudFront Storefront Distribution | Network | AWS | CDN distribution serving the public consumer storefront (React/TS). No authentication required. |
| C003 | S3 Dashboard Bucket | Storage | AWS | S3 bucket hosting Dashboard static assets. Block public access enabled, versioned, SSE-S3 encryption, access logs enabled. |
| C004 | S3 Storefront Bucket | Storage | AWS | S3 bucket hosting Storefront static assets. Block public access enabled, versioned, SSE-S3 encryption, access logs enabled. |
| C005 | S3 Access Logs Bucket | Storage | AWS | Central access logging bucket for CloudFront and S3 access logs. 90-day lifecycle, 30-day IA transition. |
| C006 | API Gateway (REST) | Network | AWS | REST API Gateway with Cognito authorizer. Serves pricing-cycles, approvals, agents/status, monitoring, products, billing, metrics, reset, seed endpoints. CORS enabled for all origins. |
| C007 | Lambda - Pricing Cycles | Compute | AWS | Python 3.12 Lambda handler for POST/GET /pricing-cycles. Invokes Orchestrator Agent via SigV4. 5-min timeout, read/write to DynamoDB, Cost Explorer access. |
| C008 | Lambda - Approvals | Compute | AWS | Python 3.12 Lambda handler for POST /approvals. Manages approval workflow, updates scenario status, applies price changes to products. |
| C009 | Lambda - Scenarios | Compute | AWS | Python 3.12 Lambda handler for scenario detail operations. Read-only access to PricingScenarios table. |
| C010 | Lambda - Agents Status | Compute | AWS | Python 3.12 Lambda handler for GET /agents/status. Provides real-time agent execution status from PricingCycles table. |
| C011 | Lambda - Monitoring | Compute | AWS | Python 3.12 Lambda handler for GET /monitoring/{scenarioId}. Reads pricing scenario monitoring data. |
| C012 | Lambda - Products | Compute | AWS | Python 3.12 Lambda handler for GET /products. Public endpoint (no auth) serving product catalog data. |
| C013 | Lambda - Metrics | Compute | AWS | Python 3.12 Lambda handler for GET /metrics. Reads CloudWatch metrics for Operations dashboard. Has cloudwatch:GetMetricData and dynamodb:Scan permissions. |
| C014 | Lambda - MCP Competitor API | Compute | AWS | MCP Server Lambda providing competitor pricing data tool interface for AI agents. 256MB, 30s timeout. |
| C015 | Lambda - MCP ERP/POS | Compute | AWS | MCP Server Lambda providing sales history, inventory, and price elasticity data for AI agents. 256MB, 30s timeout. |
| C016 | Lambda - MCP Market Signals | Compute | AWS | MCP Server Lambda providing market trends and sentiment data for AI agents. 256MB, 30s timeout. |
| C017 | Lambda - MCP Cost & Finance | Compute | AWS | MCP Server Lambda providing COGS, margins, and financial rules for AI agents. 256MB, 30s timeout. |
| C018 | Bedrock AgentCore - Orchestrator | Compute | AWS | Orchestrator agent running Claude Opus 4 on AgentCore Runtime. Coordinates 5 specialist agents, manages pricing cycle workflow, and produces final scenarios. |
| C019 | Bedrock AgentCore - Competitive Intelligence | Compute | AWS | Specialist agent (Claude Sonnet 4) analyzing competitive landscape via MCP Competitor API server. |
| C020 | Bedrock AgentCore - Demand Forecasting | Compute | AWS | Specialist agent (Claude Sonnet 4) forecasting demand using ERP/POS data via MCP server. |
| C021 | Bedrock AgentCore - Market Intelligence | Compute | AWS | Specialist agent (Claude Sonnet 4) analyzing market conditions via MCP Market Signals server. |
| C022 | Bedrock AgentCore - Strategy Synthesis | Compute | AWS | Specialist agent (Claude Sonnet 4) synthesizing pricing strategies from all intelligence inputs. |
| C023 | Bedrock AgentCore - Implementation Monitoring | Compute | AWS | Specialist agent (Claude Sonnet 4) monitoring post-implementation pricing performance and variance detection. |
| C024 | Bedrock Guardrails | Security | AWS | Amazon Bedrock Guardrails enforcing pricing compliance: blocks predatory pricing, price fixing, discrimination, and gouging. Applied to all agent outputs. |
| C025 | AgentCore Memory | Storage | AWS | AgentCore Memory service providing short-term (24h TTL) and long-term (100 cycles) memory. Scoped to Pricing Group level for data isolation. |
| C026 | AgentCore Gateway | Network | AWS | AgentCore Gateway routing agent requests to MCP Server Lambda targets. Manages tool dispatch for all 6 agents. |
| C027 | Cognito User Pool | Security | AWS | Amazon Cognito User Pool for Dashboard authentication. Email-based sign-in, self-registration disabled, RBAC groups (PricingAnalysts, Operations). JWT tokens with 1h access/id token validity, 30d refresh. |
| C028 | CloudWatch Dashboard | Other | AWS | Operational dashboard with Lambda invocation metrics, DynamoDB throughput, and API Gateway performance monitoring. |
| C029 | AWS Budgets | Other | AWS | Budget alarm for Bedrock spend with $50/month threshold and 80% notification to admin email. |

### Connections

| ID | Source | Destination | Protocol | Port | Encrypted | Description |
|---|---|---|---|---|---|---|
| CN001 | C001 | C003 | HTTPS | 443 | Yes | CloudFront Dashboard fetches static assets from S3 Dashboard bucket via OAI |
| CN002 | C002 | C004 | HTTPS | 443 | Yes | CloudFront Storefront fetches static assets from S3 Storefront bucket via OAI |
| CN003 | C001 | C005 | HTTPS | 443 | Yes | CloudFront Dashboard writes access logs to S3 Access Logs bucket |
| CN004 | C002 | C005 | HTTPS | 443 | Yes | CloudFront Storefront writes access logs to S3 Access Logs bucket |
| CN005 | C001 | C006 | HTTPS | 443 | Yes | Dashboard frontend sends authenticated API requests to API Gateway |
| CN006 | C002 | C006 | HTTPS | 443 | Yes | Storefront frontend sends public product API requests to API Gateway |
| CN007 | C006 | C027 | HTTPS | 443 | Yes | API Gateway validates JWT tokens with Cognito User Pool authorizer |
| CN008 | C006 | C007 | HTTPS | 443 | Yes | API Gateway routes /pricing-cycles requests to Pricing Cycles Lambda |
| CN009 | C006 | C008 | HTTPS | 443 | Yes | API Gateway routes /approvals requests to Approvals Lambda |
| CN010 | C006 | C009 | HTTPS | 443 | Yes | API Gateway routes scenario detail requests to Scenarios Lambda |
| CN011 | C006 | C010 | HTTPS | 443 | Yes | API Gateway routes /agents/status requests to Agents Status Lambda |
| CN012 | C006 | C011 | HTTPS | 443 | Yes | API Gateway routes /monitoring requests to Monitoring Lambda |
| CN013 | C006 | C012 | HTTPS | 443 | Yes | API Gateway routes /products requests to Products Lambda (no auth) |
| CN014 | C006 | C013 | HTTPS | 443 | Yes | API Gateway routes /metrics requests to Metrics Lambda |
| CN015 | C007 | C018 | HTTPS | 443 | Yes | Pricing Cycles Lambda invokes Orchestrator agent via SigV4-signed HTTP request to AgentCore Runtime |
| CN016 | C018 | C026 | HTTPS | 443 | Yes | Orchestrator agent dispatches tool calls through AgentCore Gateway |
| CN017 | C026 | C014 | HTTPS | 443 | Yes | AgentCore Gateway invokes MCP Competitor API Lambda for competitive data |
| CN018 | C026 | C015 | HTTPS | 443 | Yes | AgentCore Gateway invokes MCP ERP/POS Lambda for sales and inventory data |
| CN019 | C026 | C016 | HTTPS | 443 | Yes | AgentCore Gateway invokes MCP Market Signals Lambda for market trends |
| CN020 | C026 | C017 | HTTPS | 443 | Yes | AgentCore Gateway invokes MCP Cost & Finance Lambda for COGS and margins |
| CN021 | C018 | C019 | HTTPS | 443 | Yes | Orchestrator coordinates Competitive Intelligence agent on AgentCore |
| CN022 | C018 | C020 | HTTPS | 443 | Yes | Orchestrator coordinates Demand Forecasting agent on AgentCore |
| CN023 | C018 | C021 | HTTPS | 443 | Yes | Orchestrator coordinates Market Intelligence agent on AgentCore |
| CN024 | C018 | C022 | HTTPS | 443 | Yes | Orchestrator coordinates Strategy Synthesis agent on AgentCore |
| CN025 | C018 | C023 | HTTPS | 443 | Yes | Orchestrator coordinates Implementation Monitoring agent on AgentCore |
| CN026 | C018 | C024 | HTTPS | 443 | Yes | All agent outputs pass through Bedrock Guardrails for compliance validation |
| CN027 | C018 | C025 | HTTPS | 443 | Yes | Orchestrator reads/writes short-term and long-term memory via AgentCore Memory API |

### Data Stores

| ID | Name | Type | Classification | Encrypted at Rest | Description |
|---|---|---|---|---|---|
| D001 | PricingCycles Table | NoSQL | Confidential | Yes | DynamoDB table storing pricing cycle metadata and agent statuses. Partition key: cycleId, sort key: status. PAY_PER_REQUEST billing, TTL enabled, point-in-time recovery enabled, AWS-managed encryption. |
| D002 | PricingScenarios Table | NoSQL | Confidential | Yes | DynamoDB table storing generated pricing scenarios per cycle. Contains ranked pricing recommendations with confidence scores, risk classification, and projected financial impact. Partition key: cycleId, sort key: scenarioId. |
| D003 | Products Table | NoSQL | Internal | Yes | DynamoDB table for product catalog with current pricing. Partition key: productId. Contains product metadata, current prices, cost information, and MAP constraints. Read publicly via /products endpoint. |
| D004 | AuditTrail Table | NoSQL | Confidential | Yes | DynamoDB table storing guardrail evaluation audit records. Critical for regulatory compliance (FTC, Robinson-Patman Act, EU Omnibus Directive). Partition key: scenarioId, sort key: timestamp#ruleId. |
| D005 | Approvals Table | NoSQL | Confidential | Yes | DynamoDB table storing approval workflow actions (approve/reject/revert). Contains approver identity, decision rationale, and timestamps. Partition key: scenarioId, sort key: timestamp. |
| D006 | AgentCore Short-Term Memory | Object Storage | Confidential | Yes | AgentCore Memory service short-term store with 24h TTL. Holds agent intermediate outputs, request parameters, and inter-agent messages. Scoped to Pricing Group level for data isolation. |
| D007 | AgentCore Long-Term Memory | Object Storage | Confidential | Yes | AgentCore Memory service long-term store retaining last 100 cycles. Contains selected scenarios, outcomes, revenue/margin results, and approval decisions. Used for agent learning and trend analysis. |

## Threat Actors

### Insider

- **Type**: ThreatActorType.INSIDER
- **Capability Level**: CapabilityLevel.MEDIUM
- **Motivations**: Financial, Revenge
- **Resources**: ResourceLevel.LIMITED
- **Relevant**: Yes
- **Priority**: 5/10
- **Description**: An employee or contractor with legitimate access to the system

### External Attacker

- **Type**: ThreatActorType.EXTERNAL
- **Capability Level**: CapabilityLevel.MEDIUM
- **Motivations**: Financial
- **Resources**: ResourceLevel.MODERATE
- **Relevant**: Yes
- **Priority**: 3/10
- **Description**: An external individual or group attempting to gain unauthorized access

### Nation-state Actor

- **Type**: ThreatActorType.NATION_STATE
- **Capability Level**: CapabilityLevel.HIGH
- **Motivations**: Espionage, Political
- **Resources**: ResourceLevel.EXTENSIVE
- **Relevant**: Yes
- **Priority**: 1/10
- **Description**: A government-sponsored group with advanced capabilities

### Hacktivist

- **Type**: ThreatActorType.HACKTIVIST
- **Capability Level**: CapabilityLevel.MEDIUM
- **Motivations**: Ideology, Political
- **Resources**: ResourceLevel.MODERATE
- **Relevant**: Yes
- **Priority**: 6/10
- **Description**: An individual or group motivated by ideological or political beliefs

### Organized Crime

- **Type**: ThreatActorType.ORGANIZED_CRIME
- **Capability Level**: CapabilityLevel.HIGH
- **Motivations**: Financial
- **Resources**: ResourceLevel.EXTENSIVE
- **Relevant**: Yes
- **Priority**: 2/10
- **Description**: A criminal organization with significant resources

### Competitor

- **Type**: ThreatActorType.COMPETITOR
- **Capability Level**: CapabilityLevel.MEDIUM
- **Motivations**: Financial, Espionage
- **Resources**: ResourceLevel.MODERATE
- **Relevant**: Yes
- **Priority**: 7/10
- **Description**: A business competitor seeking competitive advantage

### Script Kiddie

- **Type**: ThreatActorType.SCRIPT_KIDDIE
- **Capability Level**: CapabilityLevel.LOW
- **Motivations**: Curiosity, Reputation
- **Resources**: ResourceLevel.LIMITED
- **Relevant**: Yes
- **Priority**: 9/10
- **Description**: An inexperienced attacker using pre-made tools

### Disgruntled Employee

- **Type**: ThreatActorType.DISGRUNTLED_EMPLOYEE
- **Capability Level**: CapabilityLevel.MEDIUM
- **Motivations**: Revenge
- **Resources**: ResourceLevel.LIMITED
- **Relevant**: Yes
- **Priority**: 4/10
- **Description**: A current or former employee with a grievance

### Privileged User

- **Type**: ThreatActorType.PRIVILEGED_USER
- **Capability Level**: CapabilityLevel.HIGH
- **Motivations**: Financial, Accidental
- **Resources**: ResourceLevel.MODERATE
- **Relevant**: Yes
- **Priority**: 8/10
- **Description**: A user with elevated privileges who may abuse them or make mistakes

### Third Party

- **Type**: ThreatActorType.THIRD_PARTY
- **Capability Level**: CapabilityLevel.MEDIUM
- **Motivations**: Financial, Accidental
- **Resources**: ResourceLevel.MODERATE
- **Relevant**: Yes
- **Priority**: 10/10
- **Description**: A vendor, partner, or service provider with access to the system

### Competitor / Corporate Spy

- **Type**: ThreatActorType.EXTERNAL
- **Capability Level**: CapabilityLevel.HIGH
- **Motivations**: Financial, Espionage
- **Resources**: ResourceLevel.EXTENSIVE
- **Relevant**: Yes
- **Priority**: 2/10
- **Description**: Competitors seeking to gain unfair pricing advantage by accessing proprietary pricing strategies, cost structures, demand forecasts, and competitive intelligence data.

### Malicious Insider

- **Type**: ThreatActorType.INSIDER
- **Capability Level**: CapabilityLevel.MEDIUM
- **Motivations**: Financial, Revenge
- **Resources**: ResourceLevel.MODERATE
- **Relevant**: Yes
- **Priority**: 1/10
- **Description**: Disgruntled or compromised employee (Pricing Analyst or Operations team member) with legitimate access who abuses their role to manipulate pricing, exfiltrate data, or approve fraudulent scenarios.

### Organized Cybercriminal

- **Type**: ThreatActorType.EXTERNAL
- **Capability Level**: CapabilityLevel.HIGH
- **Motivations**: Financial
- **Resources**: ResourceLevel.EXTENSIVE
- **Relevant**: Yes
- **Priority**: 3/10
- **Description**: Organized cybercriminal groups targeting financial data, pricing algorithms, and customer information for ransomware, data theft, or market manipulation schemes.

### Automated Bot / Script Kiddie

- **Type**: ThreatActorType.EXTERNAL
- **Capability Level**: CapabilityLevel.LOW
- **Motivations**: Financial, Disruption
- **Resources**: ResourceLevel.LIMITED
- **Relevant**: Yes
- **Priority**: 5/10
- **Description**: Automated scripts and bots attempting to exploit public-facing endpoints (storefront, products API) for price scraping, denial-of-service, or credential stuffing attacks.

### AI/ML Adversary

- **Type**: ThreatActorType.EXTERNAL
- **Capability Level**: CapabilityLevel.MEDIUM
- **Motivations**: Financial, Disruption
- **Resources**: ResourceLevel.MODERATE
- **Relevant**: Yes
- **Priority**: 4/10
- **Description**: Attackers targeting AI/ML components — attempting prompt injection against AI agents, manipulating MCP server data to influence pricing recommendations, or poisoning training/memory data.

### Nation-State Actor

- **Type**: ThreatActorType.NATION_STATE
- **Capability Level**: CapabilityLevel.HIGH
- **Motivations**: Political, Espionage
- **Resources**: ResourceLevel.EXTENSIVE
- **Relevant**: Yes
- **Priority**: 6/10
- **Description**: State-sponsored actors interested in economic disruption, supply chain compromise, or gaining strategic market intelligence on pricing patterns across multinational retail operations.

### Regulatory Auditor / Researcher

- **Type**: ThreatActorType.EXTERNAL
- **Capability Level**: CapabilityLevel.LOW
- **Motivations**: Political
- **Resources**: ResourceLevel.MODERATE
- **Relevant**: Yes
- **Priority**: 7/10
- **Description**: Regulatory bodies (FTC, EU regulators) or security researchers probing the system for compliance violations, pricing discrimination, or predatory pricing patterns.

## Trust Boundaries

### Trust Zones

#### Internet

- **Trust Level**: TrustLevel.UNTRUSTED
- **Description**: The public internet, considered untrusted

#### DMZ

- **Trust Level**: TrustLevel.LOW
- **Description**: Demilitarized zone for public-facing services

#### Application

- **Trust Level**: TrustLevel.MEDIUM
- **Description**: Zone containing application servers and services

#### Data

- **Trust Level**: TrustLevel.HIGH
- **Description**: Zone containing databases and data storage

#### Admin

- **Trust Level**: TrustLevel.FULL
- **Description**: Administrative zone with highest privileges

#### Public Internet

- **Trust Level**: TrustLevel.UNTRUSTED
- **Description**: Untrusted public internet zone where end users (both authenticated dashboard users and unauthenticated storefront visitors) interact with the system via browsers.

#### CDN Edge Layer

- **Trust Level**: TrustLevel.LOW
- **Description**: CloudFront CDN edge network serving static frontend assets. Enforces HTTPS, caches content, and acts as the first network boundary.

#### API Gateway Perimeter

- **Trust Level**: TrustLevel.MEDIUM
- **Description**: API Gateway with Cognito authorizer. Validates JWT tokens, enforces rate limits, and routes authenticated requests to backend Lambda handlers.

#### Backend Compute (Lambda)

- **Trust Level**: TrustLevel.HIGH
- **Description**: AWS Lambda execution environment running API handler functions. Has IAM-scoped permissions to DynamoDB and AgentCore. Trusted compute within VPC-less serverless environment.

#### AgentCore Runtime

- **Trust Level**: TrustLevel.HIGH
- **Description**: Amazon Bedrock AgentCore Runtime environment where AI agents execute. Managed by AWS, accessed via SigV4-signed requests. Contains model invocations, agent orchestration, and guardrails.

#### Data Persistence Layer

- **Trust Level**: TrustLevel.HIGH
- **Description**: Persistent data layer including DynamoDB tables and AgentCore Memory stores. Contains sensitive pricing data, audit trails, and approval records. AWS-managed encryption.

#### Identity & Access Management

- **Trust Level**: TrustLevel.HIGH
- **Description**: AWS IAM and Cognito identity services controlling authentication, authorization, and credential management across all system components.

### Trust Boundaries

#### Internet Boundary

- **Type**: BoundaryType.NETWORK
- **Controls**: Web Application Firewall, DDoS Protection, TLS Encryption
- **Description**: Boundary between the internet and internal systems

#### DMZ Boundary

- **Type**: BoundaryType.NETWORK
- **Controls**: Network Firewall, Intrusion Detection System, API Gateway
- **Description**: Boundary between public-facing services and internal applications

#### Data Boundary

- **Type**: BoundaryType.NETWORK
- **Controls**: Database Firewall, Encryption, Access Control Lists
- **Description**: Boundary protecting data storage systems

#### Admin Boundary

- **Type**: BoundaryType.NETWORK
- **Controls**: Privileged Access Management, Multi-Factor Authentication, Audit Logging
- **Description**: Boundary for administrative access

#### Internet-to-CDN Boundary

- **Type**: BoundaryType.NETWORK
- **Controls**: HTTPS/TLS encryption, CloudFront WAF (optional), Geographic restrictions
- **Description**: Boundary between public internet and AWS CDN edge. First point of contact for all user requests.

#### CDN/Public-to-API Gateway Boundary

- **Type**: BoundaryType.NETWORK
- **Controls**: Cognito JWT validation, API key (optional), CORS policy, Request throttling
- **Description**: Boundary between public/CDN layer and the API perimeter. Cognito authorizer validates tokens for authenticated endpoints; /products is unauthenticated.

#### API Gateway-to-Compute Boundary

- **Type**: BoundaryType.NETWORK
- **Controls**: IAM execution roles, Least-privilege policies, Resource-level permissions
- **Description**: Boundary between API Gateway and Lambda compute. Crossed via IAM role assumption with scoped permissions.

#### Compute-to-AgentCore Boundary

- **Type**: BoundaryType.NETWORK
- **Controls**: SigV4 request signing, IAM policies scoped to runtime ARNs, Bedrock Guardrails
- **Description**: Boundary between Lambda compute and AgentCore Runtime. SigV4-signed requests authenticate Lambda to invoke agents. Guardrails enforce content compliance.

#### Compute-to-Data Boundary

- **Type**: BoundaryType.NETWORK
- **Controls**: IAM table-level grants, Encryption at rest (AWS-managed), Point-in-time recovery
- **Description**: Boundary protecting DynamoDB tables and AgentCore Memory from compute layers. Accessed via IAM with fine-grained table/action scoping.

## Assets and Flows

### Assets

| ID | Name | Type | Classification | Sensitivity | Criticality | Owner |
|---|---|---|---|---|---|---|
| A001 | User Credentials | AssetType.CREDENTIAL | AssetClassification.CONFIDENTIAL | 5 | 5 | N/A |
| A002 | Personal Identifiable Information | AssetType.DATA | AssetClassification.CONFIDENTIAL | 4 | 4 | N/A |
| A003 | Session Token | AssetType.TOKEN | AssetClassification.CONFIDENTIAL | 5 | 5 | N/A |
| A004 | Configuration Data | AssetType.CONFIG | AssetClassification.INTERNAL | 3 | 4 | N/A |
| A005 | Encryption Keys | AssetType.KEY | AssetClassification.RESTRICTED | 5 | 5 | N/A |
| A006 | Public Content | AssetType.DATA | AssetClassification.PUBLIC | 1 | 2 | N/A |
| A007 | Audit Logs | AssetType.DATA | AssetClassification.INTERNAL | 3 | 4 | N/A |
| A008 | Pricing Scenarios & Recommendations | AssetType.DATA | AssetClassification.CONFIDENTIAL | 5 | 5 | N/A |
| A009 | Market Intelligence Data | AssetType.DATA | AssetClassification.CONFIDENTIAL | 4 | 4 | N/A |
| A010 | Product Catalog & Pricing Data | AssetType.DATA | AssetClassification.INTERNAL | 3 | 4 | N/A |
| A011 | Regulatory Audit Trail | AssetType.DATA | AssetClassification.CONFIDENTIAL | 4 | 5 | N/A |
| A012 | Authentication Credentials & Tokens | AssetType.CREDENTIAL | AssetClassification.RESTRICTED | 5 | 5 | N/A |
| A013 | Approval Workflow Decisions | AssetType.DATA | AssetClassification.CONFIDENTIAL | 4 | 4 | N/A |
| A014 | Agent Memory & Context | AssetType.DATA | AssetClassification.CONFIDENTIAL | 3 | 3 | N/A |
| A015 | System Configuration & Agent Logic | AssetType.DATA | AssetClassification.INTERNAL | 4 | 3 | N/A |
| A016 | Operational Metrics & Logs | AssetType.DATA | AssetClassification.INTERNAL | 2 | 2 | N/A |

### Asset Flows

| ID | Asset | Source | Destination | Protocol | Encrypted | Risk Level |
|---|---|---|---|---|---|---|
| F001 | User Credentials | C001 | C002 | HTTPS | Yes | 4 |
| F002 | Session Token | C002 | C001 | HTTPS | Yes | 3 |
| F003 | Personal Identifiable Information | C003 | C004 | TLS | Yes | 3 |
| F004 | Audit Logs | C003 | C005 | TLS | Yes | 2 |

## Threats

### Identified Threats

#### T1: AI/ML Adversary crafting malicious inputs

**Statement**: A AI/ML Adversary crafting malicious inputs Access to any agent input channel (MCP server responses, user-provided parameters, or memory content) can Injects adversarial prompts into MCP server data or pricing cycle parameters to manipulate agent reasoning and produce biased pricing, which leads to Agents generate manipulated pricing recommendations that bypass guardrails, causing financial loss or regulatory violations

- **Prerequisites**: Access to any agent input channel (MCP server responses, user-provided parameters, or memory content)
- **Action**: Injects adversarial prompts into MCP server data or pricing cycle parameters to manipulate agent reasoning and produce biased pricing
- **Impact**: Agents generate manipulated pricing recommendations that bypass guardrails, causing financial loss or regulatory violations
- **Impacted Assets**: A008, A009
- **Tags**: prompt-injection, ai-safety, STRIDE-T

#### T2: Malicious insider with PricingAnalysts group membership

**Statement**: A Malicious insider with PricingAnalysts group membership Valid Cognito credentials with PricingAnalysts role and knowledge of approval workflow can Approves fraudulent HIGH-risk pricing scenarios or manipulates scenario parameters before approval to benefit a specific party, which leads to Unauthorized price changes applied to production products causing financial loss, regulatory non-compliance, or competitive disadvantage

- **Prerequisites**: Valid Cognito credentials with PricingAnalysts role and knowledge of approval workflow
- **Action**: Approves fraudulent HIGH-risk pricing scenarios or manipulates scenario parameters before approval to benefit a specific party
- **Impact**: Unauthorized price changes applied to production products causing financial loss, regulatory non-compliance, or competitive disadvantage
- **Impacted Assets**: A013, A008
- **Tags**: insider-threat, approval-fraud, STRIDE-E

#### T3: External attacker targeting Cognito authentication

**Statement**: A External attacker targeting Cognito authentication Knowledge of Cognito User Pool ID and client ID (exposed in frontend config) can Performs credential stuffing or brute-force attacks against Cognito login using leaked credential databases, which leads to Unauthorized access to dashboard, ability to initiate pricing cycles, view confidential pricing strategies, or approve scenarios

- **Prerequisites**: Knowledge of Cognito User Pool ID and client ID (exposed in frontend config)
- **Action**: Performs credential stuffing or brute-force attacks against Cognito login using leaked credential databases
- **Impact**: Unauthorized access to dashboard, ability to initiate pricing cycles, view confidential pricing strategies, or approve scenarios
- **Impacted Assets**: A012
- **Tags**: credential-stuffing, authentication-bypass, STRIDE-S

#### T4: Competitor or cybercriminal targeting pricing data

**Statement**: A Competitor or cybercriminal targeting pricing data Compromised credentials or exploited vulnerability in API Gateway or Lambda handlers can Exfiltrates pricing scenarios, competitive intelligence, cost structures, and demand forecasts from DynamoDB or API responses, which leads to Loss of proprietary pricing strategies and competitive intelligence worth significant business value to competitors

- **Prerequisites**: Compromised credentials or exploited vulnerability in API Gateway or Lambda handlers
- **Action**: Exfiltrates pricing scenarios, competitive intelligence, cost structures, and demand forecasts from DynamoDB or API responses
- **Impact**: Loss of proprietary pricing strategies and competitive intelligence worth significant business value to competitors
- **Impacted Assets**: A008, A009
- **Tags**: data-exfiltration, trade-secrets, STRIDE-I

#### T5: Attacker targeting audit trail integrity

**Statement**: A Attacker targeting audit trail integrity Write access to AuditTrail or Approvals DynamoDB tables via compromised Lambda role or direct API manipulation can Modifies or deletes audit trail records to conceal unauthorized pricing changes or compliance violations, which leads to Regulatory non-compliance (FTC, EU Omnibus), inability to prove pricing decisions were lawful, legal liability

- **Prerequisites**: Write access to AuditTrail or Approvals DynamoDB tables via compromised Lambda role or direct API manipulation
- **Action**: Modifies or deletes audit trail records to conceal unauthorized pricing changes or compliance violations
- **Impact**: Regulatory non-compliance (FTC, EU Omnibus), inability to prove pricing decisions were lawful, legal liability
- **Impacted Assets**: A011
- **Tags**: audit-tampering, regulatory-risk, STRIDE-T

#### T6: Automated bot targeting public /products endpoint

**Statement**: A Automated bot targeting public /products endpoint Knowledge of API Gateway URL (publicly accessible) and product endpoint path can Sends high-volume requests to /products API to scrape entire catalog and real-time pricing or exhaust Lambda concurrency, which leads to Competitors gain real-time pricing intelligence; legitimate users experience degraded performance or service unavailability

- **Prerequisites**: Knowledge of API Gateway URL (publicly accessible) and product endpoint path
- **Action**: Sends high-volume requests to /products API to scrape entire catalog and real-time pricing or exhaust Lambda concurrency
- **Impact**: Competitors gain real-time pricing intelligence; legitimate users experience degraded performance or service unavailability
- **Impacted Assets**: A010
- **Tags**: api-abuse, rate-limiting, STRIDE-D

#### T7: AI/ML adversary targeting AgentCore Memory

**Statement**: A AI/ML adversary targeting AgentCore Memory Access to agent execution flow or ability to influence data written to AgentCore Memory via manipulated MCP responses can Poisons long-term memory with biased historical data causing agents to systematically produce skewed recommendations, which leads to Gradual degradation of pricing quality; subtle biases compound over 100 cycles creating systematic financial damage

- **Prerequisites**: Access to agent execution flow or ability to influence data written to AgentCore Memory via manipulated MCP responses
- **Action**: Poisons long-term memory with biased historical data causing agents to systematically produce skewed recommendations
- **Impact**: Gradual degradation of pricing quality; subtle biases compound over 100 cycles creating systematic financial damage
- **Impacted Assets**: A014, A008
- **Tags**: data-poisoning, memory-manipulation, STRIDE-T

#### T8: Attacker exploiting overly permissive CORS configuration

**Statement**: A Attacker exploiting overly permissive CORS configuration CORS allows ALL_ORIGINS on API Gateway; attacker creates malicious website visited by authenticated user can Exploits permissive CORS policy to make cross-origin requests from malicious site using victim's active Cognito session, which leads to Unauthorized actions on behalf of authenticated user including initiating pricing cycles or approving scenarios

- **Prerequisites**: CORS allows ALL_ORIGINS on API Gateway; attacker creates malicious website visited by authenticated user
- **Action**: Exploits permissive CORS policy to make cross-origin requests from malicious site using victim's active Cognito session
- **Impact**: Unauthorized actions on behalf of authenticated user including initiating pricing cycles or approving scenarios
- **Impacted Assets**: A012, A013
- **Tags**: cors-abuse, csrf, STRIDE-S

#### T9: Insider or attacker with AWS console access

**Statement**: A Insider or attacker with AWS console access IAM credentials with DynamoDB write permissions or compromised Lambda execution role can Directly modifies Products table to change live consumer-facing prices bypassing the entire approval workflow and guardrails, which leads to Unauthorized price changes visible to consumers; potential predatory pricing, reputational damage, regulatory penalties

- **Prerequisites**: IAM credentials with DynamoDB write permissions or compromised Lambda execution role
- **Action**: Directly modifies Products table to change live consumer-facing prices bypassing the entire approval workflow and guardrails
- **Impact**: Unauthorized price changes visible to consumers; potential predatory pricing, reputational damage, regulatory penalties
- **Impacted Assets**: A010, A013
- **Tags**: workflow-bypass, direct-db-access, STRIDE-E

#### T10: Attacker or insider targeting guardrail bypass

**Statement**: A Attacker or insider targeting guardrail bypass Understanding of guardrail rules and ability to craft scenarios that technically pass validation but are ethically problematic can Crafts inputs that produce scenarios passing automated guardrail checks but violating spirit of pricing regulations, which leads to Compliant-appearing but harmful pricing reaches production; regulatory investigation, fines, reputational damage

- **Prerequisites**: Understanding of guardrail rules and ability to craft scenarios that technically pass validation but are ethically problematic
- **Action**: Crafts inputs that produce scenarios passing automated guardrail checks but violating spirit of pricing regulations
- **Impact**: Compliant-appearing but harmful pricing reaches production; regulatory investigation, fines, reputational damage
- **Impacted Assets**: A008, A011
- **Tags**: guardrail-evasion, compliance-bypass, STRIDE-T

#### T11: External attacker targeting Lambda supply chain

**Statement**: A External attacker targeting Lambda supply chain Compromised Python dependency in requirements or malicious package in Lambda layer can Introduces malicious code via compromised dependency that exfiltrates data, modifies pricing logic, or creates backdoors, which leads to Complete compromise of backend compute; data exfiltration, pricing manipulation, persistent unauthorized access

- **Prerequisites**: Compromised Python dependency in requirements or malicious package in Lambda layer
- **Action**: Introduces malicious code via compromised dependency that exfiltrates data, modifies pricing logic, or creates backdoors
- **Impact**: Complete compromise of backend compute; data exfiltration, pricing manipulation, persistent unauthorized access
- **Impacted Assets**: A008, A009, A012
- **Tags**: supply-chain, dependency-compromise, STRIDE-T

#### T12: Attacker intercepting or replaying SigV4 requests

**Statement**: A Attacker intercepting or replaying SigV4 requests Ability to observe or reconstruct SigV4-signed requests between Lambda and AgentCore can Captures and replays SigV4-signed AgentCore invocation requests to trigger unauthorized agent executions, which leads to Unauthorized agent invocations consuming resources; potential access to confidential agent outputs and memory data

- **Prerequisites**: Ability to observe or reconstruct SigV4-signed requests between Lambda and AgentCore
- **Action**: Captures and replays SigV4-signed AgentCore invocation requests to trigger unauthorized agent executions
- **Impact**: Unauthorized agent invocations consuming resources; potential access to confidential agent outputs and memory data
- **Impacted Assets**: A012, A014
- **Tags**: replay-attack, sigv4, STRIDE-R

## Mitigations

### Identified Mitigations

#### M1: Implement input sanitization and validation on all MCP server responses before passing to agents. Add output validation on agent responses. Use Bedrock Guardrails content filters to detect and block adversarial prompt patterns in agent inputs and outputs.

**Addresses Threats**: T1

#### M2: Implement dual-approval requirement for HIGH-risk scenarios requiring two different PricingAnalysts to approve. Add separation of duties so the person initiating a pricing cycle cannot approve their own scenarios.

**Addresses Threats**: T2

#### M3: Enable Cognito Advanced Security Features with adaptive authentication, compromised credential detection, and account takeover protection. Configure MFA requirement for all dashboard users.

**Addresses Threats**: T3

#### M4: Implement field-level encryption for sensitive pricing data in DynamoDB. Use AWS KMS customer-managed keys with strict key policies. Enable DynamoDB Streams for change detection and alerting on unauthorized access patterns.

**Addresses Threats**: T4

#### M5: Make AuditTrail table immutable using DynamoDB condition expressions that prevent updates/deletes. Enable DynamoDB Streams to replicate audit records to a separate AWS account for tamper-evident storage.

**Addresses Threats**: T5

#### M6: Configure API Gateway throttling and usage plans for the public /products endpoint. Implement per-IP rate limiting, request quotas, and optional WAF rules to block scraping patterns.

**Addresses Threats**: T6

#### M7: Implement memory integrity validation with checksums on AgentCore Memory writes. Add anomaly detection on long-term memory content to identify statistical drift or poisoned entries. Periodic human review of memory content.

**Addresses Threats**: T7

#### M8: Restrict CORS policy from ALL_ORIGINS to specific allowed origins (CloudFront distribution domains only). Add CSRF token validation for state-changing operations (POST /pricing-cycles, POST /approvals).

**Addresses Threats**: T8

#### M9: Implement IAM policy conditions restricting DynamoDB writes to Products table only through the Approvals Lambda execution role. Add SCPs preventing direct console access to production tables. Enable CloudTrail data events for write operations.

**Addresses Threats**: T9

#### M10: Implement multi-layered guardrail validation: automated Bedrock Guardrails + local rules engine + statistical outlier detection on price changes. Add human review queue for edge cases that pass rules but show unusual patterns.

**Addresses Threats**: T10

#### M11: Pin all Python dependencies to exact versions in requirements.txt. Enable Dependabot/pip-audit in CI/CD pipeline. Use Lambda layers with verified checksums. Implement binary authorization for container images.

**Addresses Threats**: T11

#### M12: SigV4 signatures include timestamp (X-Amz-Date) with 5-minute validity window preventing replay attacks. Ensure Lambda requests include unique request IDs. Enable CloudTrail logging for all AgentCore API calls.

**Addresses Threats**: T12

## Assumptions

### A001: AWS Services

**Description**: Amazon Bedrock AgentCore Runtime, Gateway, and Memory services are managed by AWS and provide adequate isolation between tenants.

- **Impact**: If AgentCore has cross-tenant vulnerabilities, pricing data could leak to other AWS customers using the same service.
- **Rationale**: AWS managed services follow shared responsibility model. AgentCore is a fully managed service where AWS is responsible for infrastructure security and tenant isolation.

### A002: Authentication

**Description**: Cognito User Pool is the sole identity provider and all dashboard API access requires valid JWT tokens. Self-registration is disabled and only admins create users.

- **Impact**: If alternative authentication paths exist or tokens can be forged, the entire authorization model is undermined.
- **Rationale**: CDK code shows self_sign_up_enabled=False, API Gateway uses CognitoUserPoolsAuthorizer, and all non-/products endpoints require COGNITO auth type.

### A003: Network

**Description**: All inter-service communication occurs over AWS internal networks using HTTPS/TLS. No VPC is used for Lambda functions (they run in AWS-managed networking).

- **Impact**: Without VPC, Lambda functions have direct internet egress which could be used for data exfiltration if compromised. No network-level isolation between Lambda and public internet.
- **Rationale**: CDK code does not configure VPC for Lambda functions. AWS Lambda networking defaults to AWS-managed networking with internet access.

### A004: Data

**Description**: MCP Server data is simulated for this demo. In production, MCP servers would connect to real external data sources (competitor APIs, ERP systems, market feeds).

- **Impact**: Real external integrations introduce additional attack surface (credential management for external APIs, data integrity from untrusted sources, availability dependencies).
- **Rationale**: README states MCP servers provide simulated data. Production deployment would require additional security controls for external integrations.

### A005: AWS Services

**Description**: Bedrock Guardrails effectively catch all pricing compliance violations (predatory pricing, price fixing, discrimination, gouging) as configured.

- **Impact**: If guardrails have false negatives, non-compliant pricing could reach production and trigger regulatory penalties.
- **Rationale**: Guardrails are a defense-in-depth layer. The local guardrails.py engine provides additional validation (below-cost, MAP, geo-bias, PII), but LLM-based content filtering has inherent uncertainty.

### A006: Operations

**Description**: AWS CloudTrail is enabled for the account and captures all API calls including DynamoDB data events and Bedrock/AgentCore invocations.

- **Impact**: Without CloudTrail, incident response and forensic analysis capabilities are severely limited. Audit trail tampering would be undetectable.
- **Rationale**: CloudTrail is assumed as a baseline AWS security control. The threat model relies on CloudTrail for detection of unauthorized access and replay attacks.

### A007: Authentication

**Description**: Deploy.sh hardcoded demo credentials (DemoPass2024!, OpsPass2024!) are only used for initial setup and users are expected to change passwords or the deployment is for demo/testing only.

- **Impact**: If demo credentials remain in production, they provide a trivial authentication bypass for any attacker who reads the public repository.
- **Rationale**: deploy.sh creates users with known passwords. This is acceptable for demo/sample code but would be a critical vulnerability in production deployment.

### A008: Network

**Description**: The public /products endpoint is intentionally unauthenticated as it serves consumer-facing product catalog data that is not considered sensitive.

- **Impact**: Product pricing data is publicly accessible. Competitors can continuously monitor pricing without any barriers.
- **Rationale**: The storefront requires public access to display products. The architecture explicitly marks this as a public endpoint with read-only access to the Products table.

## Phase Progress

| Phase | Name | Completion |
|---|---|---|
| 1 | Business Context Analysis | 100% ✅ |
| 2 | Architecture Analysis | 100% ✅ |
| 3 | Threat Actor Analysis | 100% ✅ |
| 4 | Trust Boundary Analysis | 100% ✅ |
| 5 | Asset Flow Analysis | 100% ✅ |
| 6 | Threat Identification | 100% ✅ |
| 7 | Mitigation Planning | 100% ✅ |
| 7.5 | Code Validation Analysis | 0% ⏳ |
| 8 | Residual Risk Analysis | 0% ⏳ |
| 9 | Output Generation and Documentation | 100% ✅ |

---

*This threat model report was generated automatically by the Threat Modeling MCP Server.*
