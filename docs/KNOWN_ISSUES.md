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

**Fix:** The runtime containers now read the shared model configuration (`shared.model_config` → `ORCHESTRATOR_MODEL` / `SPECIALIST_MODEL`) instead of hardcoding model IDs, and `scripts/select_model.py` writes both `modelId` and `specialistModelId` to `model-config.json`. The selected model now genuinely drives all agents; both tiers default to the selected model unless `SPECIALIST_MODEL_ID` overrides the specialist tier.

**Prevention:** Keep configurable values in one shared config source that both scripts and runtime read from — never duplicate them as hardcoded constants in the runtime.
