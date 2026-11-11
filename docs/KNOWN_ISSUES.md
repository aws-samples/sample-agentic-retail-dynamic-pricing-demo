# Known Issues and Deployment Lessons Learned

This document captures issues encountered during deployment and their resolutions.

---

## 1. CDK fails with "No module named 'aws_cdk'" despite package being installed

**Symptom:** `npx cdk deploy` fails with `ModuleNotFoundError: No module named 'aws_cdk'` even though `pip list | grep aws-cdk` shows the package is installed.

**Root Cause:** CDK spawns a subprocess using `/bin/sh -c "python3 cdk/app.py"`. If the system `python3` differs from the venv's `python3` (or if `PATH` isn't inherited by the subprocess), it uses the wrong interpreter.

**Additional factor:** Paths with spaces (e.g., `Kiro Exp/Retail Dynamic Pricing - BACKUP`) can break CDK's subprocess invocation.

**Fix:** Use `--app` flag to explicitly point to the venv Python:

```bash
npx cdk deploy --all --app ".venv/bin/python3 cdk/app.py"
```

Or create a wrapper script (`run_cdk.sh`) that quotes paths correctly:

```bash
#!/bin/bash
exec "$(dirname "$0")/.venv/bin/python3" cdk/app.py "$@"
```

**Prevention:** Avoid project directory names with spaces. If unavoidable, always use the `--app` override.

---

## 2. AgentCore Runtime creation fails with ECR permissions error

**Symptom:**
```
ValidationException: Access denied while validating ECR URI '...'
The execution role requires permissions for ecr:GetAuthorizationToken,
ecr:BatchGetImage, and ecr:GetDownloadUrlForLayer operations.
```

**Root Cause:** The IAM role created by `scripts/create_agentcore_role.py` scopes ECR pull permissions to `repository/retail-pricing-*` (dash-wildcard), but the actual ECR repositories use a slash separator: `repository/retail-pricing/competitive-intelligence`.

The glob `retail-pricing-*` does not match `retail-pricing/competitive-intelligence`.

**Fix:** Add an inline policy with the correct resource pattern:

```bash
aws iam put-role-policy \
  --role-name RetailPricingAgentCoreRole \
  --policy-name ECRImagePullFix \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": [
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:BatchCheckLayerAvailability"
      ],
      "Resource": "arn:aws:ecr:us-east-1:<ACCOUNT_ID>:repository/retail-pricing/*"
    }]
  }'
```

**Prevention:** The `create_agentcore_role.py` script should be updated to use `retail-pricing/*` instead of `retail-pricing-*` in the ECR resource ARN.

---

## 3. Gateway setup fails with missing Lambda ARN environment variables

**Symptom:**
```
Error: Missing required environment variables: COMPETITOR_API_LAMBDA_ARN,
ERP_POS_LAMBDA_ARN, MARKET_SIGNALS_LAMBDA_ARN, COST_FINANCE_LAMBDA_ARN
```

**Root Cause:** `scripts/setup_gateway.py` expects 4 environment variables pointing to the MCP Server Lambda ARNs deployed by CDK. These aren't set automatically after `cdk deploy`.

**Fix:** Query the Lambda ARNs and export them before running the script:

```bash
aws lambda list-functions \
  --query "Functions[?starts_with(FunctionName, 'rdp-mcp-')].{Name:FunctionName,ARN:FunctionArn}" \
  --output table --region us-east-1

export COMPETITOR_API_LAMBDA_ARN=<ARN for rdp-mcp-competitor-api>
export ERP_POS_LAMBDA_ARN=<ARN for rdp-mcp-erp-pos>
export MARKET_SIGNALS_LAMBDA_ARN=<ARN for rdp-mcp-market-signals>
export COST_FINANCE_LAMBDA_ARN=<ARN for rdp-mcp-cost-finance>

python3 scripts/setup_gateway.py --region us-east-1
```

**Prevention:** The deployment guide should document this dependency, or the script should auto-discover the Lambda ARNs by function name prefix.

---

## 4. Gateway target synchronization reports "not supported for synchronization" for Lambda targets

**Symptom:**
```
Target type LAMBDA is not supported for synchronization
```
(when `scripts/setup_gateway.py` attempts to synchronize the MCP Server gateway targets)

**Root Cause:** Lambda-type gateway targets do **not** support synchronization at all. Synchronization is a tool-discovery mechanism for target types (such as OpenAPI/Smithy endpoints) whose tools are discovered dynamically. Lambda targets instead supply their tools via the inline `toolSchema` provided at registration time, so there is no discovery step to run — and no sync is needed for them. (The earlier belief that this was a `targetIdList` "length must be <= 1" limit was incorrect.)

**Impact:** None — targets are registered and fully functional. Agents can invoke the MCP Server Lambdas; the tools are already known from the registration `toolSchema`.

**Fix:** No action needed. `scripts/setup_gateway.py` now synchronizes targets one at a time and treats the "Target type LAMBDA is not supported for synchronization" response as **expected**, logging it and continuing rather than failing.

**Prevention:** Do not attempt to synchronize Lambda gateway targets. Rely on the inline `toolSchema` at registration to supply tools for Lambda targets.

---

## 5. AgentCore role missing Lambda invoke permissions for MCP Servers

**Symptom:**
```
ValidationException: Gateway execution role lacks permission to invoke Lambda function
arn:aws:lambda:...:function:rdp-mcp-competitor-api
```

**Root Cause:** The `create_agentcore_role.py` script does not include `lambda:InvokeFunction` permissions for the MCP Server Lambda functions. The gateway needs to invoke these Lambdas on behalf of agents.

**Fix:** Add inline policy:

```bash
aws iam put-role-policy \
  --role-name RetailPricingAgentCoreRole \
  --policy-name LambdaInvokeMcpServers \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:us-east-1:<ACCOUNT_ID>:function:rdp-mcp-*"
    }]
  }'
```

**Prevention:** The `create_agentcore_role.py` script should include Lambda invoke permissions scoped to `rdp-mcp-*` functions.

---

## 6. Pricing cycle fails with AccessDeniedException on InvokeAgentRuntime

**Symptom:**
```
AccessDeniedException: User is not authorized to perform:
bedrock-agentcore:InvokeAgentRuntime on resource: ...
```

**Root Cause:** Two issues:
1. The Lambda's `ORCHESTRATOR_AGENT_ARN` environment variable pointed to a stale ARN from a previous deployment (different account).
2. The Lambda execution role (from CDK) didn't include `bedrock-agentcore:InvokeAgentRuntime` permission — the CDK IAM policy only covers the control plane, not the data plane invoke.

**Fix:**
1. Update Lambda env var with correct orchestrator ARN from `scripts/agent_arns.env`
2. Add invoke permissions to the Lambda role:

```bash
aws iam put-role-policy \
  --role-name <PRICING_CYCLES_LAMBDA_ROLE> \
  --policy-name InvokeAgentCore \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["bedrock-agentcore:InvokeAgentRuntime", "bedrock-agentcore:InvokeAgentRuntimeForUser"],
      "Resource": "arn:aws:bedrock-agentcore:us-east-1:<ACCOUNT_ID>:runtime/*"
    }]
  }'
```

**Prevention:** The CDK stack should include `InvokeAgentRuntime` in the agentcore_policy statement, and the deploy script should automatically update the Lambda env var.

---

## 7. Pricing cycle fails with DynamoDB permission errors (Scan, BatchWriteItem)

**Symptom:** Sequential `AccessDeniedException` errors for `dynamodb:Scan` on Products table and `dynamodb:BatchWriteItem` on PricingScenarios table.

**Root Cause:** CDK's `grant_read_data()` / `grant_read_write_data()` don't include `Scan` or `BatchWriteItem` actions. The pricing cycles handler needs broader DynamoDB access than what the CDK grants provide.

**Fix:** Add a comprehensive policy covering all required actions:

```bash
aws iam put-role-policy \
  --role-name <PRICING_CYCLES_LAMBDA_ROLE> \
  --policy-name DynamoDBPricingCyclesHandler \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
        "dynamodb:Query", "dynamodb:Scan",
        "dynamodb:BatchWriteItem", "dynamodb:BatchGetItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:<ACCOUNT_ID>:table/PricingCycles",
        "arn:aws:dynamodb:us-east-1:<ACCOUNT_ID>:table/PricingScenarios",
        "arn:aws:dynamodb:us-east-1:<ACCOUNT_ID>:table/Products",
        "arn:aws:dynamodb:us-east-1:<ACCOUNT_ID>:table/Approvals",
        "arn:aws:dynamodb:us-east-1:<ACCOUNT_ID>:table/AuditTrail"
      ]
    }]
  }'
```

**Prevention:** CDK should use explicit `PolicyStatement` with all required actions instead of relying on `grant_*` helper methods.

---

## 8. /billing endpoint missing from API Gateway (CORS error)

**Symptom:** TCO tab shows "Loading billing data..." and browser console shows CORS error for `/billing` endpoint.

**Root Cause:** The `/billing` route handler exists in `pricing_cycles.py` but was never registered as an API Gateway route in the CDK stack. The Lambda handles it internally, but API Gateway rejects the preflight OPTIONS request with no CORS headers.

**Fix:** Added `/billing` GET route to `cdk/stacks/api_handlers.py` pointing to the pricing_cycles Lambda, then redeployed CDK.

**Prevention:** Ensure all routes handled by Lambda code are also registered in the API Gateway CDK construct.

---

## 9. Cognito redirect_mismatch error on login

**Symptom:** Login redirects to Cognito but returns `error=redirect_mismatch`.

**Root Cause:** Two issues:
1. No Cognito domain was configured (needed for hosted UI OAuth flows)
2. The app client's callback URLs didn't include the `/callback` path that the frontend uses

**Fix:**
1. Create the domain: `aws cognito-idp create-user-pool-domain --domain <unique-name>`
2. Update callback URLs to include `/callback` path:

```bash
aws cognito-idp update-user-pool-client \
  --callback-urls '["https://<CLOUDFRONT_DOMAIN>/callback"]' \
  --logout-urls '["https://<CLOUDFRONT_DOMAIN>"]'
```

**Prevention:** CDK should configure the Cognito domain and set callback URLs based on the CloudFront distribution domain.

---

## 10. Cognito Advanced Security fails with ESSENTIALS pricing tier

**Symptom:**
```
Resource handler returned message: "The following features need to be disabled
for the ESSENTIALS pricing tier configured: Threat Protection"
```

**Root Cause:** The Cognito User Pool was created on the ESSENTIALS pricing tier. `AdvancedSecurityMode.ENFORCED` (Threat Protection) requires the **Plus** pricing tier ($0.0150/MAU vs $0.0065/MAU for Essentials).

**Fix:** Removed `advanced_security_mode=cognito.AdvancedSecurityMode.ENFORCED` from the CDK Cognito construct. MFA (TOTP) remains enabled as it works on all tiers and provides the primary defense against credential stuffing.

Because the User Pool intentionally stays on the ESSENTIALS tier, the corresponding cdk-nag findings are suppressed in `cdk/app.py` as the same accepted limitation:
- **`AwsSolutions-COG3`** — Advanced Security Mode (Threat Protection) not ENFORCED.
- **`AwsSolutions-COG8`** — Cognito not on the Plus pricing tier.

Both suppressions document that MFA (TOTP) is the compensating control, and that Threat Protection requires the Plus tier which this demo does not use.

**Prevention:** Before enabling Cognito Advanced Security features, verify the User Pool pricing tier supports it. For production workloads where compromised credential detection is critical, upgrade to the Plus tier via the AWS Console before deploying with `AdvancedSecurityMode.ENFORCED` (and remove the COG3/COG8 suppressions).

---

---

## Deployment Issues Encountered (July 2026 Redeploy)

### Issue: Cognito Requires Email as Username

**Symptom:** `InvalidParameterException: Username should be an email` when creating Cognito users with plain usernames like `admin1`.

**Root Cause:** The Retail project's Cognito User Pool is configured with `username_attributes: [email]`, requiring email format for usernames.

**Fix:** Use email-format usernames:
```bash
aws cognito-idp admin-create-user --user-pool-id <POOL_ID> \
  --username "admin@demo.example" --temporary-password 'TempPassword1!' \
  --message-action SUPPRESS
```

---

### Issue: Cognito Password Policy Stricter Than Expected

**Symptom:** `InvalidPasswordException: Password did not conform with password policy: Password not long enough` when using `TempPass1!`.

**Root Cause:** The CDK-configured password policy requires a minimum of 12 characters.

**Fix:** Use a longer temporary password (12+ chars):
```bash
--temporary-password 'TempPassword1!'   # 14 chars - works
--password 'DemoTest123!'               # permanent password
```

---

### Issue: Cognito Group Names Don't Match Documentation

**Symptom:** `ResourceNotFoundException: Group not found` when trying to add user to `ProductManagers`.

**Root Cause:** The CDK creates groups named `PricingAnalysts` and `Operations`, not `ProductManagers`.

**Fix:** Check actual group names before assigning:
```bash
aws cognito-idp list-groups --user-pool-id <POOL_ID> --query "Groups[].GroupName"
# Returns: PricingAnalysts, Operations
```

---

### Issue: CDK `destroy` Exits with Code 1 Even on Success

**Symptom:** `npx cdk destroy --all --force` returns exit code 1, but stacks are actually deleted.

**Root Cause:** CDK CLI process terminates before CloudFormation confirms deletion. The actual deletion continues in the background.

**Fix:** After CDK destroy exits, verify with:
```bash
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query "StackSummaries[?contains(StackName, 'Retail')].StackName"
```
If empty, deletion succeeded.

---

### Issue: S3 Buckets Must Be Emptied Before Stack Deletion

**Symptom:** Stack deletion fails or hangs with S3 bucket resources in `DELETE_FAILED` state.

**Root Cause:** CloudFormation cannot delete non-empty S3 buckets even with `RemovalPolicy.DESTROY`.

**Fix:** Empty buckets before running `cdk destroy`:
```bash
aws s3 rm s3://<bucket-name>/ --recursive
```

---

### Issue: Cognito Redirect Mismatch After Fresh Deploy

**Symptom:** Clicking "Login" on the dashboard shows `error=redirect_mismatch&client_id=...` in the browser.

**Root Cause:** The Cognito User Pool Client's callback URLs only include `localhost:5173` (for local dev). The CloudFront distribution domain is not added as a callback URL during CDK deploy.

**Fix:** Add the CloudFront domain to the Cognito app client's callback URLs:
```bash
aws cognito-idp update-user-pool-client \
  --user-pool-id <POOL_ID> --client-id <CLIENT_ID> \
  --callback-urls "http://localhost:5173/callback" "https://localhost:5173/callback" "https://<CLOUDFRONT_DOMAIN>/callback" \
  --logout-urls "http://localhost:5173" "https://localhost:5173" "https://<CLOUDFRONT_DOMAIN>" \
  --supported-identity-providers COGNITO \
  --allowed-o-auth-flows code \
  --allowed-o-auth-scopes openid email profile \
  --allowed-o-auth-flows-user-pool-client
```

**Prevention:** The CDK stack should derive callback URLs from the CloudFront distribution domain. This requires the Cognito client to depend on the CloudFront distribution resource. Update `cdk/stacks/auth.py` to include the CloudFront URL in callback_urls.

---

## Validation Deploy Fixes

The following issues were found and fixed during a clean end-to-end validation deploy. Each is resolved in the current codebase; entries are kept for future reference.

### Issue: `cdk deploy` fails with "No module named 'cdk_nag'"

**Symptom:** `npx cdk deploy` (or `cdk synth`) aborts immediately with `ModuleNotFoundError: No module named 'cdk_nag'`.

**Root Cause:** `cdk/app.py` applies `cdk-nag` AwsSolutionsChecks, but `cdk-nag` was missing from `pyproject.toml`, so it was never installed into the venv.

**Fix:** Added `cdk-nag` to the project dependencies in `pyproject.toml`. It now installs automatically as part of `pip install -r requirements.txt`.

**Prevention:** Keep every module imported by the CDK app declared as a project dependency. A synth in CI catches missing CDK dependencies before deploy.

---

### Issue: `cdk-nag` 3.x breaks with an ImportError on `NagSuppressions`

**Symptom:** With an unpinned `cdk-nag`, installing a 3.x release causes an `ImportError` for `NagSuppressions` when `cdk/app.py` is loaded.

**Root Cause:** `cdk-nag` 3.x removed `NagSuppressions` from the top-level module API, so the existing import in `cdk/app.py` no longer resolves.

**Fix:** Pinned the dependency to `cdk-nag>=2.35.0,<3.0.0` in `pyproject.toml` so the 2.x top-level API (including `NagSuppressions`) is used.

**Prevention:** Pin CDK ecosystem libraries to a compatible major version and bump deliberately after verifying API compatibility.

---

### Issue: AgentCore gateway target registration fails while the gateway is still creating

**Symptom:**
```
gateway is in CREATING status
```
when `scripts/setup_gateway.py` tries to register the MCP Server targets right after creating the gateway.

**Root Cause:** Target registration was attempted before the newly-created AgentCore gateway had finished provisioning and reached a READY state.

**Fix:** `scripts/setup_gateway.py` now waits for the gateway to reach READY before registering targets, and registers/synchronizes targets one at a time. (See issue #4 — the "Target type LAMBDA is not supported for synchronization" message during this step is expected and non-fatal.)

**Prevention:** Always poll for a resource's READY/ACTIVE state before performing dependent operations against it.

---

### Issue: Storefront `npm install` fails with ERESOLVE dependency conflict

**Symptom:** `npm install` in `frontend/storefront` fails with an `ERESOLVE` peer-dependency error; the storefront could not be built.

**Root Cause:** The storefront pinned `vite@8` together with `@vitejs/plugin-react@4.7.0`, which is incompatible with Vite 8. The dashboard was on Vite 5, so the two frontends were also inconsistent with each other.

**Fix:** Aligned both frontends (`frontend/dashboard` and `frontend/storefront`) on the same validated versions: `vite` 8.3.0, `@vitejs/plugin-react` 5.2.0, and `react-router-dom` 7.18.4. Both frontends now build cleanly and `npm audit` reports 0 vulnerabilities on each.

**Prevention:** Keep shared frontend tooling versions aligned across both apps and verify `npm install`/`npm run build` plus `npm audit` on a clean checkout.

---

### Issue: Python dependency versions not reproducible across deploys

**Symptom:** Deploys resolved different transitive dependency versions on different machines, making builds hard to reproduce.

**Root Cause:** Dependencies were installed via `pip install -e .` alone, without a pinned, validated dependency set.

**Fix:** The root `requirements.txt` is now the pinned/validated dependency set. `deploy.sh` installs it explicitly (`pip install -r requirements.txt`, then `pip install -e . --no-deps`), and `pip-audit` runs against `requirements.txt`.

**Prevention:** Install from the pinned `requirements.txt` and treat it as the source of truth for dependency versions; regenerate and re-validate it when dependencies change.

---

### Issue: Model selection did not reach the deployed agents

**Symptom:** Running `scripts/select_model.py` (or choosing a model during deploy) appeared to have no effect — the deployed agents kept using their original model IDs.

**Root Cause:** The AgentCore runtime containers hardcoded their model IDs (e.g. `us.anthropic.claude-opus-4-7` / `claude-sonnet-4-6`) instead of reading the selected configuration, so `select_model.py` was effectively a no-op for the deployed agents.

**Fix:** The runtime containers now read the shared model configuration (`shared.model_config` → `ORCHESTRATOR_MODEL` / `SPECIALIST_MODEL`) instead of hardcoding model IDs, and `scripts/select_model.py` writes both `modelId` and `specialistModelId` to `model-config.json`. The selected models now genuinely drive the agents. (At the time one selection was written to both tiers; see "Model selection set the same model for all six agents" below for the tiered selection.)

**Prevention:** Keep configurable values in one shared config source that both scripts and runtime read from — never duplicate them as hardcoded constants in the runtime.

---
### Issue: `cdk destroy` fails to delete the access-logs S3 bucket ("bucket not empty")
**Symptom:** During teardown, `cdk destroy` fails with `DELETE_FAILED` on the hosting access-logs S3 bucket: "The bucket you tried to delete is not empty", even though the buckets were emptied moments earlier.
**Root Cause:** The access-logs bucket continuously receives CloudFront and S3 server access logs from the dashboard/storefront buckets. New log objects land in it between the time it is emptied and the time CloudFormation tries to delete it, so it is non-empty again at deletion.
**Fix:** `teardown.sh` re-empties all `retaildynamicpricing-*` buckets immediately before each `cdk destroy` attempt and retries the destroy up to 3 times. Running teardown again also clears it, since by the retry the log-producing distributions are already being removed.
**Prevention:** When deleting buckets that receive access logs, empty them as late as possible (right before delete) and retry; do not rely on a single up-front empty.

---
### Issue: `npm audit` reports findings in the tailwindcss build-tool dependency chain
**Symptom:** Running `npm audit` in `frontend/dashboard` or `frontend/storefront` reports several findings (e.g. `braces`, `micromatch`, `fast-glob`, `chokidar`, `postcss-selector-parser`, `source-map-js`) pulled in transitively by `tailwindcss`. These are **not** reported by GitHub Dependabot and are distinct from the application dependencies (axios, PyJWT) that Dependabot tracks.
**Root Cause:** These packages are build-time tooling for Tailwind/PostCSS. They run only during `npm run build` to generate the static CSS/JS and are **not included in the deployed `dist/` bundle**. The advisories are ReDoS / CPU-exhaustion issues reachable only when an attacker controls the build inputs (glob patterns, selectors) — not a runtime exposure for a static frontend built by the project owner.
**Fix:** Intentionally deferred. The only `npm audit fix --force` remediation bumps `tailwindcss` to a new major version, which carries breaking changes (config format and utility-class changes) that would require re-validating both frontends' styling. We do not bundle a breaking major upgrade into routine security-patch merges.
**Prevention / when to act:** If a fully clean `npm audit` is required, perform a dedicated Tailwind major upgrade on its own branch: bump `tailwindcss` and its chain, rebuild both frontends, and visually verify the dashboard and storefront before merging. Treat it as a tracked UI task, not a dependency-patch.
**Status (resolved without a major upgrade):** patched releases inside Tailwind 3's version ranges (`postcss-selector-parser` 6.1.5, `source-map-js` 1.2.2) now clear these findings, and `npm audit` reports 0 vulnerabilities in both frontends on `tailwindcss` 3.4.19. A Tailwind 4 upgrade is no longer needed for security; do it only for its features.

---

## Post-Deploy Fixes

Defects found by checking a finished `./deploy.sh` run against the live account. Each is fixed in the current codebase; entries are kept for future reference.

### Issue: Dependency scan crashed but `deploy.sh` printed "No known vulnerabilities found"

**Symptom:** Step 1.5 showed a `pip-audit` traceback (`ensurepip ... died with <Signals.SIGABRT: 6>`) immediately followed by `✓ No known vulnerabilities found in dependencies`. A real finding (`multidict` 6.9.0, CVE-2026-104874, fixed in 6.9.1) was never reported.
**Root Cause:** The scan was `if pip-audit ... | tail -5; then`, which tests the exit status of `tail`, not `pip-audit`, so it always passed. Separately, `pip-audit`'s default mode builds a temporary virtualenv to resolve `-r requirements.txt`, and that step aborted on this host.
**Fix:** Step 1.5 now audits the pinned set directly (`--no-deps --disable-pip --strict`, no temporary venv), tests `pip-audit`'s own exit status, and reports exactly one of: no known vulnerabilities (✓), vulnerabilities found (listed, deploy continues), or scan could not run (warning, never ✓). It also audits the dependency set the agent containers would install (resolved with `pip install --dry-run`, because `backend/agents/agentcore/requirements.txt` is unpinned). `multidict` was bumped to 6.9.1 at the time; it has since been removed entirely, along with the unused package that pulled it in (see "Unused `strands-agents-tools` pulled in vulnerable Pillow, aiohttp and multidict" below).
**Prevention:** Never pipe a gate command into another command inside an `if`; capture the output and test the real status.

### Issue: Agents deployed without the gateway and memory (no MCP tools, memory disabled)

**Symptom:** `get-agent-runtime` returned no `environmentVariables` for any runtime. Agents answered from the model alone ("AGENTCORE_MEMORY_ID not set; memory disabled for this agent" was only logged at DEBUG, so nothing surfaced), and the orchestrator image could not start (`KeyError` on the five `*_AGENT_ARN` variables).
**Root Cause:** `deploy.sh` deployed the agents (Step 3) before the gateway and memory existed (Step 5), and `scripts/deploy_agentcore.py` never set `AGENTCORE_GATEWAY_ENDPOINT` / `AGENTCORE_MEMORY_ID` (or the model IDs, or the specialist ARNs) on the runtimes. The gateway code path had never run against a real endpoint and had its own defects: `MCPClient.streamable_http` does not exist (use `MCPClient(url=<gatewayUrl>/mcp)`), `get_guardrail_config()` returned kwargs that `strands.Agent` rejects (`TypeError`; guardrails belong on `BedrockModel`), and the runtime role had no AgentCore Memory or `InvokeAgentRuntime` permissions.
**Fix:** `deploy.sh` now creates the IAM role, gateway and memory (Step 3) before deploying the agents (Step 4) and re-deploying CDK (Step 5). `deploy_agentcore.py` discovers the gateway and memory by name, exits non-zero before building anything if either is missing, and sets the environment variables on every runtime on create and update. The role policy gains scoped memory, runtime-invoke, gateway-invoke and `ApplyGuardrail` statements (re-run `create_agentcore_role.py` to update an existing role in place). `verify_deployment.py` now fails if any runtime lacks the gateway/memory variables. If the default Bedrock guardrail does not exist in the account, the agents are deployed with `DISABLE_BEDROCK_GUARDRAILS=true` and a warning.
**Prevention:** Create dependencies before the resources that consume them, and make the verification gate check the wiring, not only that the resources exist.

### Issue: Gateway tool calls always returned `MISSING_TOOL`

**Symptom:** Calling any tool through the AgentCore Gateway reached the MCP Lambda but returned an error body with code `MISSING_TOOL`.
**Root Cause:** For Lambda targets the gateway passes the tool arguments as the Lambda event and the tool name in `context.client_context.custom["bedrockAgentCoreToolName"]` (`<target>___<tool>`). The four handlers only understood the direct-invoke shape `{"tool": ..., "params": {...}}`.
**Fix:** Each handler falls back to the gateway shape when the event has no `tool` field; the direct-invoke contract is unchanged.
**Prevention:** Test Lambda targets with the context object the gateway actually sends (see `tests/test_mcp_gateway_invocation.py`).

### Issue: Every agent image ran the competitive-intelligence agent

**Symptom:** The six images were built from one Dockerfile but all started `competitive_intelligence_runtime`.
**Root Cause:** `deploy_agentcore.py` passed `--build-arg AGENT_MODULE=...`, but the Dockerfile declares `ARG AGENT_ENTRYPOINT`; the unknown build arg was silently ignored and the default won.
**Fix:** The script passes `--build-arg AGENT_ENTRYPOINT=<module>`.
**Prevention:** After building, check `docker inspect` shows the expected `AGENT_ENTRYPOINT` for each image.

### Issue: `setup_memory.py` was not idempotent

**Symptom:** Re-running `deploy.sh` could create a second AgentCore Memory or abort.
**Root Cause:** The existing-memory check treated `list_memories()` (a list) as a dict, swallowed the resulting error, matched on a `name` field the summaries do not have, and compared against the base name while the real ID carries a random suffix (`RetailDynamicPricingMemory-Ab12Cd34Ef`).
**Fix:** The check now matches on the ID prefix, reuses the existing memory, and lets lookup errors fail the script instead of falling through to create.
**Prevention:** Look resources up by what the API actually returns, and never create after a failed lookup.

---

## Dependency Hygiene

Dependency findings from a review of the open Dependabot PRs and alerts. Each entry is either fixed or deliberately deferred with a trigger for when to act.

### Issue: Unused `strands-agents-tools` pulled in vulnerable Pillow, aiohttp and multidict

**Symptom:** Dependabot reported 50 open alerts on `requirements.txt` (41 Pillow including 5 critical, 8 aiohttp, 1 multidict). Dependabot's Pillow 13.0.0 PR made `pip install -r requirements.txt` fail with `ResolutionImpossible`.
**Root Cause:** `strands-agents-tools` was declared in `requirements.txt`, `pyproject.toml` and `backend/agents/agentcore/requirements.txt`, but no code imports `strands_tools`. It was the only package requiring Pillow, aiohttp, multidict and 24 other packages, and it caps `pillow<13.0.0` (even in its latest release), so the Pillow fixes could not be installed. The same vulnerable Pillow also shipped inside all six agent container images, which Dependabot does not scan.
**Fix:** Removed `strands-agents-tools` from all three files and dropped the 27 pins only it needed (also removed from `THIRD-PARTY-LICENSES`). The container requirements no longer floor `multidict`, because nothing installs it now.
**Prevention:** Before bumping a vulnerable transitive dependency, check what requires it (`pip show <pkg>` / the resolver report); an unused parent is cheaper to remove than to patch around.

### Issue: Dependabot single-package bumps break `pip install`

**Symptom:** Dependabot PRs that bump one pin in `requirements.txt` (e.g. `opentelemetry-api` 1.45.1, `mcp` 2.2.0) fail `pip install -r requirements.txt` with `ResolutionImpossible`, which breaks `deploy.sh` Step 1.
**Root Cause:** `requirements.txt` pins the full resolved set, and some packages are versioned together: `opentelemetry-sdk` and `opentelemetry-semantic-conventions` require an exact `opentelemetry-api` version, and `mcp` requires an exact `mcp-types` version. Dependabot bumps only the one package.
**Fix:** The OpenTelemetry packages are bumped as a group (`opentelemetry-api` / `-sdk` 1.45.1; `-semantic-conventions`, `-instrumentation`, `-instrumentation-threading` 0.66b1). Close single-package Dependabot PRs for grouped packages and bump the group instead.
**Prevention:** Before merging any dependency PR, run `pip install --dry-run -r requirements.txt` (or `deploy.sh` Step 1) on its branch.

### Issue: `mcp` 2.1.1 has open advisories but cannot be upgraded yet

**Symptom:** Dependabot and `pip-audit` report `mcp` 2.1.1 (fixed in 2.2.0).
**Root Cause:** `strands-agents` (including its latest release, 1.62.0) requires `mcp<2.2`, so 2.2.0 cannot be installed alongside it.
**Fix:** Intentionally deferred, alert dismissed as tolerable risk. The Dependabot-tracked advisory is in the MCP server StreamableHTTP transport; this project only uses the MCP client (`strands.tools.mcp.MCPClient`), and the agents connect only to this deployment's own AgentCore Gateway, which limits the client-side advisories (cross-origin redirects, server-chosen `$ref` URLs) to a server you control.
**Prevention / when to act:** When a `strands-agents` release allows `mcp>=2.2`, bump `strands-agents`, `mcp` and `mcp-types` together and re-run the tests and `pip-audit`.

### Issue: Competitor API price-variance tests failed intermittently

**Symptom:** `test_competitor_price_points_within_variance` and `test_history_prices_within_10_percent_variance` failed occasionally (e.g. `assert 5.391 <= 5.39`), with a price a fraction of a cent outside the variance band.
**Root Cause:** The handler rounds prices to 2 decimals, so a random price at the edge of the band can round to a value up to 0.005 outside it. All four variance-bound tests in `tests/test_competitor_api_handler.py` had the same exact-bound check.
**Fix:** The four tests share a `_variance_bounds()` helper that widens the band by a 0.005 rounding tolerance.
**Prevention:** When asserting bounds on rounded values, allow for the rounding.

### Issue: Every deploy re-uploaded the Lambda assets

**Symptom:** `cdk deploy` uploaded and updated the MCP server and API handler Lambdas on every run, even with no code changes.
**Root Cause:** `Code.from_asset` packaged the whole handler directory, including `__pycache__` files that change on every local test run, so the asset hash changed each time.
**Fix:** Both stacks exclude `**/__pycache__` and `**/*.pyc` from the Lambda assets.
**Prevention:** Exclude build and cache artifacts from every `Code.from_asset` directory.

### Issue: Agent containers still resolve OpenTelemetry 1.44.0

**Symptom:** `pip-audit` on the agent container dependency set (Step 1.5 audits it) reports `opentelemetry-api` 1.44.0 (CVE-2026-114603, unbounded tracestate parsing) and `opentelemetry-propagator-jaeger` 1.44.0 (CVE-2026-116694, unbounded memory in Jaeger baggage propagation), although the host `requirements.txt` pins 1.45.1. Dependabot does not report these, because it does not scan `backend/agents/agentcore/requirements.txt`.
**Root Cause:** `aws-opentelemetry-distro` (including its latest release, 0.21.0) pins `opentelemetry-api`, `opentelemetry-sdk` and `opentelemetry-propagator-jaeger` to exactly `==1.44.0`. Overriding the pin would break the distro.
**Fix:** Intentionally deferred. Both advisories need attacker-controlled trace headers; the agent runtimes are reached only through IAM-authenticated `InvokeAgentRuntime` calls from this deployment's own Lambda and orchestrator, so an outside caller cannot send them crafted `tracestate` or baggage headers.
**Prevention / when to act:** When an `aws-opentelemetry-distro` release allows OpenTelemetry 1.45.1 or later, rebuild the agent images (the file is unpinned, so the next deploy picks it up) and confirm Step 1.5's container audit is clean.

---

## Model Selection

### Issue: Model selection set the same model for all six agents

**Symptom:** Step 1.7 asked for one model and deployed it to all six agents, although the README described a tiered strategy (Opus for the orchestrator, Sonnet for the specialists). Setting `SPECIALIST_MODEL_ID` before `deploy.sh` had no effect.
**Root Cause:** `scripts/select_model.py` wrote the single selection to both `modelId` and `specialistModelId`. `deploy_agentcore.py` reads only `model-config.json`, so a `SPECIALIST_MODEL_ID` in the deploy shell never reached the agents (the variable is only read inside the runtimes, from what `deploy_agentcore.py` sets).
**Fix:** `select_model.py` now asks twice: the orchestrator model (recommended: newest ACTIVE Opus) and the specialist model (recommended: newest ACTIVE Sonnet). Pressing Enter twice, or `--non-interactive`, takes the recommended pair. `ORCHESTRATOR_MODEL_ID` / `SPECIALIST_MODEL_ID` in the environment skip the matching prompt. Strategy Synthesis is a specialist (`SPECIALIST_MODEL`), and the README now says so.
**Prevention:** `tests/test_select_model.py` covers the two prompts, the overrides and the config `deploy_agentcore.py` reads.

### Issue: The recommended model was not the newest one

**Symptom:** With Claude Opus 5.5, 5 and 4.8 available, Step 1.7 recommended Claude Opus 4.5.
**Root Cause:** Models were ranked by the release date inside the model ID. Newer IDs carry no date (`claude-opus-5-5`), so they sorted below older dated IDs (`claude-opus-4-5-20251101-v1:0`).
**Fix:** Ranking now uses the model version parsed from the ID (major, minor), then the date.
**Prevention:** The sort is covered by `tests/test_select_model.py` with a mix of dated and undated IDs.

### Issue: `switch_model.sh` said a skipped redeploy would still apply the new model

**Symptom:** Skipping the redeploy printed "Agents will use the new model on next cold start", but the agents kept their old models. A failed redeploy was also reported as "✓ Agents redeployed".
**Root Cause:** `model-config.json` is not in the agent images; the models reach the agents only as environment variables set by `deploy_agentcore.py`. The redeploy was piped into `tail -5`, so the script tested `tail`'s exit status instead of the deploy's.
**Fix:** The messages now say the change applies only after a redeploy, the redeploy output is no longer piped, and the summary shows both models.
**Prevention:** Never pipe a command whose exit status matters into another command.

---

## Authorization

### Issue: Any signed-in account could approve scenarios and change live prices (CWE-862)

**Symptom:** An account whose only Cognito group was Operations (documented as metrics and health only) could call `POST /approvals` with `action: APPROVED` and get HTTP 200. The scenario was recorded as approved by that account, and every product in its `priceChanges` had its live `currentPrice` overwritten, including HIGH risk scenarios given a 50+ character justification. Reported by the security team (CVSS 3.1 8.0 High).
**Root Cause:** API Gateway's Cognito authorizer only checks that the caller is a signed-in user of the pool, not which group they are in. The approvals handler checked separation of duties (the cycle initiator cannot approve) and the HIGH risk justification length, but never checked `cognito:groups` before approving or rejecting. The revert path did check for Operations, but only after the approval record, audit entry and scenario status had already been written, and with a substring match (`"Operations" in groups`) that accepted names such as "NotOperations".
**Fix:** `backend/api_handlers/approvals.py` checks the role first, before any read or write: approve or reject requires **PricingAnalysts**, and `revertPrices` requires **Operations**. Group names are matched exactly (`backend/api_handlers/cognito_claims.py`). Everyone else gets 403 and nothing is written. The dashboard hides the approve/reject controls from users outside PricingAnalysts and the revert button from users outside Operations (the API remains the enforcement point). 500 responses no longer return exception text.
**Prevention:** Every endpoint that changes state needs an explicit, deny-by-default role check before its first write, with exact group matching. `tests/test_approvals_authorization.py` reproduces the reported proof of concept.
**Note for existing deployments:** the demo users created by `deploy.sh` keep their access (the demo user is in PricingAnalysts; the ops user is in Operations and PricingAnalysts). An account in Operations only, such as one created by following `docs/QUICK_START.md`, can no longer approve or reject.
