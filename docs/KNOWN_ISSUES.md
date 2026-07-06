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

## 4. Gateway target synchronization fails with list length constraint

**Symptom:**
```
ValidationException: 1 validation error detected: Value '[...]' at 'targetIdList'
failed to satisfy constraint: Member must have length less than or equal to 1
```

**Root Cause:** `scripts/setup_gateway.py` passes all 4 target IDs to `SynchronizeGatewayTargets` in one call, but the API only accepts 1 target per synchronization request.

**Impact:** Low — targets are still registered and functional. Agents can invoke MCP servers. The sync step just triggers tool discovery which happens automatically on first use.

**Fix:** Non-blocking. If needed, sync targets individually:

```bash
# Targets are already registered and usable without explicit sync
```

**Prevention:** The script should loop over targets and sync one at a time.

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

**Prevention:** Before enabling Cognito Advanced Security features, verify the User Pool pricing tier supports it. For production workloads where compromised credential detection is critical, upgrade to the Plus tier via the AWS Console before deploying with `AdvancedSecurityMode.ENFORCED`.

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
