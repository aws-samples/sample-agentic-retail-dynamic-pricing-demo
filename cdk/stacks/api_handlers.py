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
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- REST API ---
        self.api = apigw.RestApi(
            self,
            "PricingApi",
            rest_api_name="retail-dynamic-pricing-api",
            description="REST API for Retail Dynamic Pricing system",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=[
                    "https://<DASHBOARD_CLOUDFRONT_DOMAIN>",
                    "https://<STOREFRONT_CLOUDFRONT_DOMAIN>",
                    "http://localhost:5173",
                ],
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Amz-Date",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                ],
                allow_credentials=True,
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
                "bedrock:InvokeAgent",
                "bedrock:InvokeAgentRuntime",
                "bedrock-agentcore:InvokeAgentRuntime",
                "bedrock-agentcore:*",
            ],
            resources=["*"],
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
        dynamodb_tables.pricing_scenarios_table.grant_read_data(self.pricing_cycles_fn)
        self.pricing_cycles_fn.add_to_role_policy(agentcore_policy)
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

        # Approvals handler
        self.approvals_fn = self._create_handler(
            "Approvals",
            "approvals",
            "Handles POST /approvals - approval workflow",
            environment={
                "APPROVALS_TABLE": dynamodb_tables.approvals_table.table_name,
                "PRICING_SCENARIOS_TABLE": dynamodb_tables.pricing_scenarios_table.table_name,
                "PRODUCTS_TABLE": dynamodb_tables.products_table.table_name,
                "AWS_REGION_NAME": cdk.Aws.REGION,
            },
        )
        dynamodb_tables.approvals_table.grant_read_write_data(self.approvals_fn)
        dynamodb_tables.pricing_scenarios_table.grant_read_write_data(self.approvals_fn)
        dynamodb_tables.products_table.grant_read_write_data(self.approvals_fn)
        self.approvals_fn.add_to_role_policy(agentcore_policy)

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
        products_resource = self.api.root.add_resource("products")
        products_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.products_fn),
        )

        # GET /products/{id} (public, no auth)
        product_id_resource = products_resource.add_resource("{id}")
        product_id_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.products_fn),
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
