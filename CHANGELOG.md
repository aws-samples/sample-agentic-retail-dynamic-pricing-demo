# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed
- Bumped dashboard dev dependencies to patched versions to clear vulnerability alerts: `browserslist` 4.28.8, `nanoid` 3.3.18, `postcss-selector-parser` 6.1.4 (non-breaking `npm audit fix`)
- Bumped storefront dev dependencies to patched versions: `browserslist` 4.28.8, `nanoid` 3.3.18 (targeted update; storefront builds clean with zero audit findings)
- Aligned both frontends on the same validated tooling: `vite` 8.3.0, `@vitejs/plugin-react` 5.2.0, `react-router-dom` 7.18.4 (dashboard was on Vite 5); `npm audit` now reports 0 vulnerabilities on both
- Frontend hosting is S3 + CloudFront only — removed the unused AWS Amplify apps from the hosting stack; stack outputs now expose only `DashboardCloudFrontUrl` / `StorefrontCloudFrontUrl` (the `DashboardAmplifyAppId` / `StorefrontAmplifyAppId` outputs are gone)
- Model selection now drives all agents: the AgentCore runtime containers read the shared model config (`ORCHESTRATOR_MODEL` / `SPECIALIST_MODEL`) instead of hardcoding model IDs, and `scripts/select_model.py` writes both `modelId` and `specialistModelId` to `model-config.json`
- `deploy.sh` now installs the pinned/validated root `requirements.txt` (`pip install -r requirements.txt`, then `pip install -e . --no-deps`) and runs `pip-audit` against `requirements.txt` for reproducible dependency resolution
- `deploy.sh` now fails loudly on real gateway/memory errors (removed the non-critical warning swallow) and runs `verify_deployment.py` as a gate (Step 9.5) before declaring success

### Fixed
- Added `cdk-nag` to `pyproject.toml` (pinned `cdk-nag>=2.35.0,<3.0.0`) — it was missing, so `cdk deploy` failed with `ModuleNotFoundError: No module named 'cdk_nag'`; the `<3.0.0` pin avoids the 3.x removal of `NagSuppressions` from the top-level API
- `scripts/setup_gateway.py` now waits for the AgentCore gateway to reach READY before registering targets (previously failed with "gateway is in CREATING status") and synchronizes targets one at a time, treating "Target type LAMBDA is not supported for synchronization" as expected (Lambda targets get their tools from the inline `toolSchema` at registration)
- Resolved the storefront `npm install` ERESOLVE conflict (`vite@8` was incompatible with `@vitejs/plugin-react@4.7.0`) via the frontend dependency alignment above
- Corrected the Bedrock IAM resource ARNs in `create_agentcore_role.py` — replaced a malformed ARN with proper foundation-model and inference-profile ARNs

### Security
- Added non-production sample-code disclaimer to the README Security section
- Suppress `AwsSolutions-COG8` alongside the existing `AwsSolutions-COG3` as the same accepted Cognito Essentials-tier limitation (Threat Protection / Plus tier not used; MFA-TOTP is the compensating control)

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
