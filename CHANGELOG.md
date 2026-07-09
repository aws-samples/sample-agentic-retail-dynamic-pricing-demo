# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-07-07

### Added
- 6 AI agents on Amazon Bedrock AgentCore (Orchestrator on Opus 4.7, 5 specialists on Sonnet 4.6)
- 4 MCP Server Lambdas (Competitor API, ERP/POS, Market Signals, Cost and Finance)
- Multi-agent orchestration with parallel intelligence gathering, 120s timeout, 2 retries, graceful degradation
- Strategy Synthesis generating 5 ranked pricing scenarios per cycle (Aggressive Growth, Market Share Capture, Balanced Optimization, Margin Protection, Conservative Protection)
- Application-layer guardrails: below-cost rejection, MAP compliance, geographic bias detection, PII protection
- Risk classification (LOW/MEDIUM/HIGH) with status labels (Recommended/Review Required/Human Exception Handling)
- Approval workflow with separation of duties (initiator cannot approve)
- Implementation Monitoring agent with variance detection (10% revenue, 3pp margin thresholds)
- Session management with SHA-256 memory integrity hashing (fail-closed on tamper)
- React Dashboard with tabs: Overview, Simulations, Analytics, Audit Trail, Predictions, Scheduling, Operations
- Public Storefront showing live product prices (unauthenticated)
- Cognito authentication with MFA REQUIRED (TOTP)
- CDK infrastructure (Python) with cdk-nag AwsSolutionsChecks
- Price Prediction Simulator with What-If Analysis
- TCO dashboard with live AWS Cost Explorer integration
- Intelligent Pricing Scheduler with event-driven triggers
- Audit trail with immutable records (IAM Deny on DeleteItem/UpdateItem)
- Input sanitization for prompt injection (7 regex patterns, agent output + MCP response scanning)
- DynamoDB Streams on Products table for change detection
- Configurable model selection via scripts/select_model.py
- STRIDE threat model with 12 threats and 12 mitigations
- Comprehensive documentation (Architecture, Demo Script, Quick Start, Known Issues)

### Security
- Bedrock Guardrails (content filtering, anti-competitive strategy blocking)
- Server-side risk level validation (prevents governance bypass via client tampering)
- CORS restricted to known CloudFront origins + localhost
- Rate limiting on public /products endpoint (100 burst / 50 sustained)
- pip-audit vulnerability scanning in deploy.sh
- git-secrets configured with AWS patterns
