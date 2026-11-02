# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `evals/`: specialist model evaluation. `python -m evals.run_eval` runs the seven dashboard presets through the real orchestrator and specialist code on each model configuration, scores the runs (deterministic checks and a blind LLM judge) and writes a report. Nothing runs without `--yes`; `--rescore` scores a saved run again
- `docs/architecture.drawio`: two-page architecture diagram (the deployed architecture with one pricing cycle traced in numbered steps, and the agents with their gateway tools, Memory, Bedrock and the guardrail)
- Configurable pricing-cycle timeouts: `deploy.sh --specialist-timeout` / `--synthesis-timeout` (or `SPECIALIST_TIMEOUT_SECONDS` / `SYNTHESIS_TIMEOUT_SECONDS`, defaults 300 / 180). `shared/cycle_timeouts.py` derives the orchestrator, Lambda and stale-cycle values from them, and `verify_deployment.py` fails if the deployed orchestrator and Lambda disagree
- `deploy.sh --alert-email` (or `ALERT_EMAIL`) for the Bedrock spend alert. On a terminal the script asks for it; without one (CI) it fails before Step 0

### Security
- The AgentCore Gateway requires SigV4 (`AWS_IAM` inbound auth). It accepted unauthenticated calls before (authorizer `NONE`), so anyone with its URL could call every tool. A gateway's authorizer cannot be changed after creation, so `scripts/setup_gateway.py` creates `retail-pricing-gateway-iam`, the agents sign their MCP calls (`backend/agents/agentcore/gateway_auth.py`), and `deploy.sh` Step 4.5 (`scripts/secure_gateway.py`) deletes the old `retail-pricing-gateway` once every agent uses the new one. `verify_deployment.py` fails while an unsigned call works or the old gateway exists
- The gateway has its own service role, `RetailPricingGatewayRole`, which can only invoke the `rdp-mcp-*` Lambdas; the agents' role no longer invokes Lambdas. Both trust policies carry `aws:SourceAccount` / `aws:SourceArn` conditions against the confused-deputy problem
- The CDK stack creates the Bedrock guardrail (Standard tier: four denied topics and a prompt-attack filter) and a published version, and `deploy_agentcore.py` attaches it to the five model-backed agents. An agent with neither a guardrail nor `DISABLE_BEDROCK_GUARDRAILS=true` now fails instead of running unguarded, and `verify_deployment.py` checks every runtime uses the stack's version. `scripts/check_guardrail.py` runs sample prompts against it
- `deploy.sh` Step 9, and the matching README / QUICK_START command, turned the implicit OAuth grant back on for the dashboard app client, which the CDK stack disables. They now keep the authorization code flow only
- Paid pricing cycles are capped: the API stage defaults to 50 rps / burst 100, `POST /pricing-cycles` to 1 rps / burst 2, and the handler returns 429 while 3 cycles are running (`MAX_ACTIVE_CYCLES`)
- Frontend dependencies bumped in both the dashboard and storefront: `vite` 8.3.4, `follow-redirects` 1.16.2, `source-map-js` 1.2.2, `postcss-selector-parser` 6.1.5. `npm audit` now reports 0 vulnerabilities in both apps (including dev dependencies), still on `tailwindcss` 3.4.19

### Changed
- Model selection is tiered: `scripts/select_model.py` (Step 1.7) asks for the orchestrator model (recommended: newest ACTIVE Opus) and the specialist model for the five specialists (recommended: newest ACTIVE Sonnet), so most model calls run on the faster, cheaper tier. `--non-interactive` takes the recommended pair, and `ORCHESTRATOR_MODEL_ID` / `SPECIALIST_MODEL_ID` in the environment skip the matching prompt. `model-config.json` gains `specialistModelName`
- `scripts/switch_model.sh` asks for both models and shows both in its summary
- Bumped dashboard dev dependencies to patched versions to clear vulnerability alerts: `browserslist` 4.28.8, `nanoid` 3.3.18, `postcss-selector-parser` 6.1.4 (non-breaking `npm audit fix`)
- Bumped storefront dev dependencies to patched versions: `browserslist` 4.28.8, `nanoid` 3.3.18 (targeted update; storefront builds clean with zero audit findings)
- Aligned both frontends on the same validated tooling: `vite` 8.3.0, `@vitejs/plugin-react` 5.2.0, `react-router-dom` 7.18.4 (dashboard was on Vite 5); `npm audit` now reports 0 vulnerabilities on both
- Frontend hosting is S3 + CloudFront only — removed the unused AWS Amplify apps from the hosting stack; stack outputs now expose only `DashboardCloudFrontUrl` / `StorefrontCloudFrontUrl` (the `DashboardAmplifyAppId` / `StorefrontAmplifyAppId` outputs are gone)
- Model selection now drives all agents: the AgentCore runtime containers read the shared model config (`ORCHESTRATOR_MODEL` / `SPECIALIST_MODEL`) instead of hardcoding model IDs, and `scripts/select_model.py` writes both `modelId` and `specialistModelId` to `model-config.json`
- `deploy.sh` now installs the pinned/validated root `requirements.txt` (`pip install -r requirements.txt`, then `pip install -e . --no-deps`) and runs `pip-audit` against `requirements.txt` for reproducible dependency resolution
- `deploy.sh` now fails loudly on real gateway/memory errors (removed the non-critical warning swallow) and runs `verify_deployment.py` as a gate (Step 9.5) before declaring success

- `deploy.sh` now creates the AgentCore IAM role, gateway and memory (Step 3) before deploying the agents (Step 4) and re-deploying CDK (Step 5); `scripts/deploy_agentcore.py` discovers the gateway and memory by name, exits non-zero before building anything if either is missing, and sets `AGENTCORE_GATEWAY_ENDPOINT` (the gateway's `/mcp` URL), `AGENTCORE_MEMORY_ID`, the model IDs, guardrail settings and (orchestrator) the specialist ARNs as environment variables on every runtime, on create and update
- `scripts/verify_deployment.py` now fails if any of the six runtimes lacks `AGENTCORE_GATEWAY_ENDPOINT` / `AGENTCORE_MEMORY_ID` on the version its DEFAULT endpoint serves
- `scripts/create_agentcore_role.py` adds scoped AgentCore Memory data-plane, `InvokeAgentRuntime` (orchestrator to specialists), `InvokeGateway` and `bedrock:ApplyGuardrail` permissions; re-running it updates an existing role in place
### Removed
- Removed the unused `strands-agents-tools` dependency (no code imports `strands_tools`) from `requirements.txt`, `pyproject.toml` and `backend/agents/agentcore/requirements.txt`, plus the 27 pins only it required, including Pillow, aiohttp, multidict and yarl. This also removes the vulnerable Pillow from the agent container images. The container `multidict` floor is gone, since nothing installs it now
### Security
- Clears 51 Dependabot alerts on `requirements.txt` (41 Pillow, 8 aiohttp, 1 multidict, 1 opentelemetry-api) by the removal above and by bumping the OpenTelemetry packages as a group: `opentelemetry-api` / `opentelemetry-sdk` 1.45.1, `opentelemetry-semantic-conventions` / `opentelemetry-instrumentation` / `opentelemetry-instrumentation-threading` 0.66b1
- Bumped `certifi` to 2026.10.23 (PYSEC-2026-4320: bundled emSign root CAs with compromised intermediate CA keys). Found by `pip-audit`; not yet raised by Dependabot
- `mcp` stays at 2.1.1: `strands-agents` (latest 1.62.0) still requires `mcp<2.2`. Deferred and documented in `docs/KNOWN_ISSUES.md`
- The agent containers still resolve OpenTelemetry 1.44.0, because `aws-opentelemetry-distro` (latest 0.21.0) pins it exactly. Deferred and documented in `docs/KNOWN_ISSUES.md`
### Fixed
- Step 1.7 recommended an older model (e.g. Claude Opus 4.5 over Opus 5.5): models are now ranked by the version in the model ID, not only by the release date, which newer IDs no longer carry
- `scripts/switch_model.sh` claimed a skipped redeploy would apply the new model "on next cold start" (it does not: the models reach the agents only through `deploy_agentcore.py`), and reported a failed redeploy as success because the redeploy was piped into `tail`
- The README listed Strategy Synthesis on the Opus tier; it is a specialist and uses the specialist model
- Docs no longer state that Bedrock Guardrails are always enforced: README, `docs/ARCHITECTURE.md` and `docs/DEMO_SCRIPT.md` now say the guardrail is optional, is not created by the demo, and is attached only when `BEDROCK_GUARDRAIL_ID` names one that exists
- The competitor API price-variance tests no longer fail intermittently: all four variance-bound checks now allow for the handler's 2-decimal rounding
- Lambda assets are no longer re-uploaded on every deploy: `Code.from_asset` excludes `__pycache__` / `*.pyc`
- `deploy.sh` Step 1.5 reported "No known vulnerabilities found" even when `pip-audit` crashed (it tested the exit status of `tail`). It now audits the pinned set with `--no-deps --disable-pip --strict`, tests `pip-audit`'s own exit status, and reports clean / vulnerabilities found / scan could not run; it also audits the agent container dependency set
- Bumped `multidict` to 6.9.1 (CVE-2026-104874) and floored it in `backend/agents/agentcore/requirements.txt`
- Agents were deployed without the gateway and memory: `MCPClient.streamable_http` does not exist (now `MCPClient(url=...)`), the guardrail was passed to `strands.Agent` (now attached to `BedrockModel`), and `AGENTCORE_MEMORY_ID not set` was logged at DEBUG (now WARNING)
- The MCP server Lambdas now understand the AgentCore Gateway invocation shape (tool arguments as the event, tool name in the Lambda context); previously every gateway tool call returned `MISSING_TOOL`
- `deploy_agentcore.py` passed an ignored `AGENT_MODULE` build arg, so every image ran the competitive-intelligence agent; it now passes `AGENT_ENTRYPOINT`. A failed runtime update is no longer swallowed
- `scripts/setup_memory.py` is idempotent again (matches the existing memory by ID prefix instead of creating a duplicate)
- Added `cdk-nag` to `pyproject.toml` (pinned `cdk-nag>=2.35.0,<3.0.0`) — it was missing, so `cdk deploy` failed with `ModuleNotFoundError: No module named 'cdk_nag'`; the `<3.0.0` pin avoids the 3.x removal of `NagSuppressions` from the top-level API
- `scripts/setup_gateway.py` now waits for the AgentCore gateway to reach READY before registering targets (previously failed with "gateway is in CREATING status") and synchronizes targets one at a time, treating "Target type LAMBDA is not supported for synchronization" as expected (Lambda targets get their tools from the inline `toolSchema` at registration)
- Resolved the storefront `npm install` ERESOLVE conflict (`vite@8` was incompatible with `@vitejs/plugin-react@4.7.0`) via the frontend dependency alignment above
- Corrected the Bedrock IAM resource ARNs in `create_agentcore_role.py` — replaced a malformed ARN with proper foundation-model and inference-profile ARNs
- Every pricing cycle analysed `default_category` / `balanced`: `rdp-api-pricing-cycles` nested the cycle parameters in a JSON `prompt` string. It now sends them at the top level, and the orchestrator still accepts the old shape
- Pricing cycles re-ran agents: both AgentCore clients kept botocore's 60 s read timeout and SDK retries (strategy synthesis takes 70–85 s), the orchestrator discarded results that took over 120 s, and Lambda retried the asynchronous invocation. Read timeouts are now set per hop, only the orchestrator retries (and only fast, retryable failures), and the Lambda has 720 s and no async retries
- The Bedrock budget filtered on "Amazon Bedrock", but Claude usage is billed as "Amazon Bedrock Service" (and AgentCore separately), so it saw about 2 % of the spend, and its only subscriber was `admin@example.com`. It now covers all three services and alerts the `--alert-email` address
- A cycle whose run died stayed `ANALYZING` forever; reads now report and store it as `FAILED` after 900 s
- Agent model calls had no output-token limit of their own. With the pinned `strands-agents` 1.56 (tests and `evals/`) no `maxTokens` was sent, Bedrock stopped Claude answers at 4,096 tokens and the agents failed with `MaxTokensReachedException`; the agent images (`strands-agents` 1.63) sent 128,000, which Bedrock reserves from the tokens-per-minute quota on every call. The five model-backed agents now set `max_tokens` 16,000 (`shared/model_config.py`)
- The guardrail's prompt-attack filter blocked legitimate strategy-synthesis prompts, because the analyst reports in them read like instructions. Strategy Synthesis now screens only the cycle's objectives and constraints as guardrail input; the reports were already screened as model output by the agents that wrote them

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
