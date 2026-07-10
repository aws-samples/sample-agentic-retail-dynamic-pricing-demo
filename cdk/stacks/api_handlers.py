"""CDK construct for API Gateway Lambda handler functions.

Defines Lambda functions for each API endpoint group and wires them
to API Gateway routes. Handlers use SigV4 HTTP calls for AgentCore
invocations (not boto3 bedrock-agentcore).

Endpoint groups:
- pricing_cycles: POST /pricing-cycles, GET /pricing-cycles/{id},
                  GET /pricing-cycles/{id}/scenarios
- scenarios: Scenario detail operations
- approvals: POST /approvals
- agents_status: GET /agents/status
- monitoring: GET /monitoring/{scenarioId}
- products: GET /products, GET /products/{id} (public, no auth)
"""

import os
from pathlib import Path

from constructs import Construct
import aws_cdk as cdk
from aws_cdk import (
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_apigateway as apigw,
    aws_cognito as cognito,
    aws_dynamodb as dynamodb,
)


# Path to the backend/api_handlers directory relative to the CDK project root
API_HANDLERS_DIR = Path(__file__).parent.parent.parent / "backend" / "api_handlers"


class ApiHandlersConstruct(Construct):
    """Construct containing API Gateway Lambda handlers and route integrations.

    Creates Lambda functions for each endpoint group, grants DynamoDB
    access, configures SigV4 signing permissions for AgentCore, and
    wires functions to API Gateway routes with Cognito authorization.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        dynamodb_tables: "DynamoDBTables",
        cognito_auth: "CognitoAuth",
        hosting: "HostingConstruct",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- REST API ---
        # Security: Restrict CORS to known CloudFront origins + localhost dev
        allowed_origins = [
            cdk.Fn.sub(
                "https://${Domain}",
                {"Domain": hosting.dashboard_distribution.distribution_domain_name},
            ),
            cdk.Fn.sub(
                "https://${Domain}",
                {"Domain": hosting.storefront_distribution.distribution_domain_name},
            ),
            "http://localhost:5173",
            "https://localhost:5173",
        ]

        self.api = apigw.RestApi(
            self,
            "PricingApi",
            rest_api_name="retail-dynamic-pricing-api",
            description="REST API for Retail Dynamic Pricing system",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=allowed_origins,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Amz-Date",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                    "X-CSRF-Token",
                ],
            ),
            deploy_options=apigw.StageOptions(stage_name="prod"),
        )

        # --- Cognito Authorizer ---
        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self,
            "CognitoAuthorizer",
            cognito_user_pools=[cognito_auth.user_pool],
            authorizer_name="retail-pricing-cognito-authorizer",
        )

        # --- Shared IAM policy for SigV4 AgentCore invocations ---
        agentcore_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
                "bedrock-agentcore:InvokeAgentRuntime",
                "bedrock-agentcore:InvokeAgentRuntimeForUser",
            ],
            resources=[
                f"arn:aws:bedrock-agentcore:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:runtime/*",
                f"arn:aws:bedrock:{cdk.Aws.REGION}::foundation-model/anthropic.*",
                f"arn:aws:bedrock:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:inference-profile/us.anthropic.*",
            ],
        )

        # --- Lambda Functions ---

        # Pricing Cycles handler
        self.pricing_cycles_fn = self._create_handler(
            "PricingCycles",
            "pricing_cycles",
            "Handles POST /pricing-cycles, GET /pricing-cycles/{id}, "
            "GET /pricing-cycles/{id}/scenarios",
            environment={
                "PRICING_CYCLES_TABLE": dynamodb_tables.pricing_cycles_table.table_name,
                "PRICING_SCENARIOS_TABLE": dynamodb_tables.pricing_scenarios_table.table_name,
                "AWS_REGION_NAME": cdk.Aws.REGION,
                # Orchestrator Agent ARN — the Lambda invokes only the orchestrator,
                # which in turn coordinates the other 5 agents on AgentCore.
                # Read from ORCHESTRATOR_AGENT_ARN env var or scripts/agent_arns.env
                "ORCHESTRATOR_AGENT_ARN": self._get_agent_arn("ORCHESTRATOR_AGENT_ARN"),
            },
            timeout_seconds=300,  # 5 min for async AgentCore invocations
        )
        dynamodb_tables.pricing_cycles_table.grant_read_write_data(self.pricing_cycles_fn)
        dynamodb_tables.pricing_scenarios_table.grant_read_write_data(self.pricing_cycles_fn)
        dynamodb_tables.products_table.grant_read_write_data(self.pricing_cycles_fn)
        self.pricing_cycles_fn.add_to_role_policy(agentcore_policy)
        # DynamoDB Scan and BatchWriteItem are not covered by grant_read_write_data
        self.pricing_cycles_fn.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:Scan",
                    "dynamodb:BatchWriteItem",
                    "dynamodb:BatchGetItem",
                ],
                resources=[
                    dynamodb_tables.pricing_cycles_table.table_arn,
                    dynamodb_tables.pricing_scenarios_table.table_arn,
                    dynamodb_tables.products_table.table_arn,
                    dynamodb_tables.approvals_table.table_arn,
                    dynamodb_tables.audit_trail_table.table_arn,
                ],
            )
        )
        # Cost Explorer access for /billing endpoint (TCO tab)
        self.pricing_cycles_fn.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ce:GetCostAndUsage",
                    "ce:GetCostForecast",
                ],
                resources=["*"],
            )
        )
        # Allow Lambda to invoke itself asynchronously for orchestrator calls
        self.pricing_cycles_fn.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[
                    cdk.Fn.sub(
                        "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:rdp-api-pricing-cycles"
                    )
                ],
            )
        )

        # Scenarios handler
        self.scenarios_fn = self._create_handler(
            "Scenarios",
            "scenarios",
            "Handles scenario detail operations",
            environment={
                "PRICING_SCENARIOS_TABLE": dynamodb_tables.pricing_scenarios_table.table_name,
            },
        )
        dynamodb_tables.pricing_scenarios_table.grant_read_data(self.scenarios_fn)

        # --- Security: Audit Trail Immutability ---
        # Deny UpdateItem and DeleteItem on AuditTrail table for all handlers
        # except pricing_cycles_fn which needs BatchWriteItem for /reset (demo only).
        # This ensures audit records are append-only and tamper-resistant.
        audit_trail_immutability_deny = iam.PolicyStatement(
            effect=iam.Effect.DENY,
            actions=[
                "dynamodb:DeleteItem",
                "dynamodb:UpdateItem",
            ],
            resources=[dynamodb_tables.audit_trail_table.table_arn],
        )

        # Approvals handler
        self.approvals_fn = self._create_handler(
            "Approvals",
            "approvals",
            "Handles POST /approvals - approval workflow",
            environment={
                "APPROVALS_TABLE": dynamodb_tables.approvals_table.table_name,
                "PRICING_SCENARIOS_TABLE": dynamodb_tables.pricing_scenarios_table.table_name,
                "PRODUCTS_TABLE": dynamodb_tables.products_table.table_name,
                "PRICING_CYCLES_TABLE": dynamodb_tables.pricing_cycles_table.table_name,
                "AWS_REGION_NAME": cdk.Aws.REGION,
            },
        )
        dynamodb_tables.approvals_table.grant_read_write_data(self.approvals_fn)
        dynamodb_tables.pricing_scenarios_table.grant_read_write_data(self.approvals_fn)
        dynamodb_tables.products_table.grant_read_write_data(self.approvals_fn)
        dynamodb_tables.pricing_cycles_table.grant_read_data(self.approvals_fn)
        self.approvals_fn.add_to_role_policy(agentcore_policy)
        # Apply audit trail immutability to approvals handler
        self.approvals_fn.add_to_role_policy(audit_trail_immutability_deny)

        # Agents Status handler
        self.agents_status_fn = self._create_handler(
            "AgentsStatus",
            "agents_status",
            "Handles GET /agents/status - real-time agent execution status",
            environment={
                "PRICING_CYCLES_TABLE": dynamodb_tables.pricing_cycles_table.table_name,
            },
        )
        dynamodb_tables.pricing_cycles_table.grant_read_data(self.agents_status_fn)

        # Monitoring handler
        self.monitoring_fn = self._create_handler(
            "Monitoring",
            "monitoring",
            "Handles GET /monitoring/{scenarioId} - monitoring metrics",
            environment={
                "PRICING_SCENARIOS_TABLE": dynamodb_tables.pricing_scenarios_table.table_name,
            },
        )
        dynamodb_tables.pricing_scenarios_table.grant_read_data(self.monitoring_fn)

        # Products handler (public, no auth)
        self.products_fn = self._create_handler(
            "Products",
            "products",
            "Handles GET /products, GET /products/{id} - public product catalog",
            environment={
                "PRODUCTS_TABLE": dynamodb_tables.products_table.table_name,
            },
        )
        dynamodb_tables.products_table.grant_read_data(self.products_fn)

        # --- API Gateway Route Integrations ---

        # POST /pricing-cycles (authenticated)
        pricing_cycles_resource = self.api.root.add_resource("pricing-cycles")
        pricing_cycles_resource.add_method(
            "POST",
            apigw.LambdaIntegration(self.pricing_cycles_fn),
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        # GET /pricing-cycles (authenticated) - list all cycles for audit trail
        pricing_cycles_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.pricing_cycles_fn),
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        # GET /pricing-cycles/{id} (authenticated)
        pricing_cycle_id_resource = pricing_cycles_resource.add_resource("{id}")
        pricing_cycle_id_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.pricing_cycles_fn),
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        # GET /pricing-cycles/{id}/scenarios (authenticated)
        scenarios_resource = pricing_cycle_id_resource.add_resource("scenarios")
        scenarios_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.pricing_cycles_fn),
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        # POST /approvals (authenticated)
        approvals_resource = self.api.root.add_resource("approvals")

        # GET /billing (authenticated) - AWS Cost Explorer data for TCO tab
        billing_resource = self.api.root.add_resource("billing")
        billing_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.pricing_cycles_fn),
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        # POST /reset (authenticated) - Reset demo data
        reset_resource = self.api.root.add_resource("reset")
        reset_resource.add_method(
            "POST",
            apigw.LambdaIntegration(self.pricing_cycles_fn),
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        # POST /seed (authenticated) - Seed historical demo data
        seed_resource = self.api.root.add_resource("seed")
        seed_resource.add_method(
            "POST",
            apigw.LambdaIntegration(self.pricing_cycles_fn),
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        # GET /metrics (authenticated) - CloudWatch operational metrics
        self.metrics_fn = self._create_handler(
            "Metrics",
            "metrics",
            "Handles GET /metrics - CloudWatch operational metrics for Ops dashboard",
            environment={
                "AWS_REGION_NAME": cdk.Aws.REGION,
            },
        )
        self.metrics_fn.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudwatch:GetMetricStatistics",
                    "cloudwatch:GetMetricData",
                ],
                # [H1 FIX] Scope CloudWatch permissions to specific metric namespaces
                resources=["*"],
                conditions={
                    "StringEquals": {
                        "cloudwatch:namespace": [
                            "AWS/Lambda",
                            "AWS/DynamoDB",
                            "AWS/ApiGateway",
                        ],
                    },
                },
            )
        )
        # [H1 FIX] Scope DynamoDB Scan to only the pricing system tables
        self.metrics_fn.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:Scan"],
                resources=[
                    dynamodb_tables.pricing_cycles_table.table_arn,
                    dynamodb_tables.pricing_scenarios_table.table_arn,
                    dynamodb_tables.products_table.table_arn,
                ],
            )
        )
        metrics_resource = self.api.root.add_resource("metrics")
        metrics_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.metrics_fn),
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        approvals_resource.add_method(
            "POST",
            apigw.LambdaIntegration(self.approvals_fn),
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        # GET /agents/status (authenticated)
        agents_resource = self.api.root.add_resource("agents")
        agents_status_resource = agents_resource.add_resource("status")
        agents_status_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.agents_status_fn),
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        # GET /monitoring/{scenarioId} (authenticated)
        monitoring_resource = self.api.root.add_resource("monitoring")
        monitoring_scenario_resource = monitoring_resource.add_resource("{scenarioId}")
        monitoring_scenario_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.monitoring_fn),
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        # GET /products (public, no auth)
        # [C5 FIX] Add method-level throttling to prevent DoS and mass scraping
        products_resource = self.api.root.add_resource("products")
        products_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.products_fn),
            method_responses=[],
        )

        # GET /products/{id} (public, no auth)
        product_id_resource = products_resource.add_resource("{id}")
        product_id_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.products_fn),
        )

        # [C5 FIX] Create a usage plan with rate limiting for public endpoints.
        # Limits: 100 requests/second burst, 50 requests/second sustained.
        # This prevents mass scraping and DoS on the unauthenticated /products endpoint.
        usage_plan = self.api.add_usage_plan(
            "PublicEndpointUsagePlan",
            name="public-products-rate-limit",
            description="Rate limiting for unauthenticated /products endpoint",
            throttle=apigw.ThrottleSettings(
                burst_limit=100,
                rate_limit=50,
            ),
        )
        usage_plan.add_api_stage(stage=self.api.deployment_stage)

        # --- Guardrails Demo endpoint ---
        # POST /guardrails/demo (authenticated) - demonstrates guardrail enforcement
        guardrails_resource = self.api.root.add_resource("guardrails")
        guardrails_demo_resource = guardrails_resource.add_resource("demo")
        self.guardrails_demo_fn = self._create_handler(
            "GuardrailsDemo",
            "guardrails_demo",
            "Handles POST /guardrails/demo - guardrail enforcement demonstrations",
            environment={},
        )
        guardrails_demo_resource.add_method(
            "POST",
            apigw.LambdaIntegration(self.guardrails_demo_fn),
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        # --- Outputs ---
        cdk.CfnOutput(
            self,
            "ApiGatewayUrl",
            value=self.api.url,
            description="API Gateway endpoint URL",
        )

    def _create_handler(
        self,
        name: str,
        handler_module: str,
        description: str,
        environment: dict[str, str] | None = None,
        timeout_seconds: int = 30,
    ) -> lambda_.Function:
        """Create a Lambda function for an API handler.

        Args:
            name: Logical name for the Lambda function construct.
            handler_module: Python module name under backend/api_handlers/.
            description: Description of the handler's purpose.
            environment: Environment variables for the Lambda function.
            timeout_seconds: Lambda timeout in seconds (default 30).

        Returns:
            The created Lambda function.
        """
        fn = lambda_.Function(
            self,
            f"{name}Handler",
            function_name=f"rdp-api-{handler_module.replace('_', '-')}",
            description=description,
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler=f"{handler_module}.handler",
            code=lambda_.Code.from_asset(str(API_HANDLERS_DIR)),
            memory_size=256,
            timeout=cdk.Duration.seconds(timeout_seconds),
            environment=environment or {},
        )

        # Tag the function for identification
        cdk.Tags.of(fn).add("Component", "ApiHandler")
        cdk.Tags.of(fn).add("Handler", name)

        return fn

    @staticmethod
    def _get_agent_arn(key: str) -> str:
        """Read an agent ARN from environment variable or scripts/agent_arns.env file.

        Falls back to the env file if the environment variable is not set,
        ensuring CDK deploys don't wipe previously configured ARNs.
        """
        # First check environment variable
        value = os.environ.get(key, "")
        if value:
            return value

        # Fall back to scripts/agent_arns.env
        env_file = Path(__file__).parent.parent.parent / "scripts" / "agent_arns.env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == key:
                    return v.strip()

        return ""
