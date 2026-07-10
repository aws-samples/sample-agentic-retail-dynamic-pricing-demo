"""Tests for CDK stack synthesis."""

import aws_cdk as cdk
from aws_cdk.assertions import Template, Match

from stacks.pricing_stack import RetailDynamicPricingStack


def test_stack_creates_successfully():
    """Verify the stack synthesizes without errors."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")
    template = Template.from_stack(stack)
    assert template is not None


def test_dynamodb_tables_created():
    """Verify all 5 DynamoDB tables are created."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")
    template = Template.from_stack(stack)

    template.resource_count_is("AWS::DynamoDB::Table", 5)


def test_pricing_cycles_table():
    """Verify PricingCycles table has correct key schema and billing mode."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")
    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "PricingCycles",
            "KeySchema": [
                {"AttributeName": "cycleId", "KeyType": "HASH"},
                {"AttributeName": "status", "KeyType": "RANGE"},
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
    )


def test_pricing_scenarios_table():
    """Verify PricingScenarios table has correct key schema and billing mode."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")
    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "PricingScenarios",
            "KeySchema": [
                {"AttributeName": "cycleId", "KeyType": "HASH"},
                {"AttributeName": "scenarioId", "KeyType": "RANGE"},
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
    )


def test_products_table():
    """Verify Products table has correct key schema and billing mode."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")
    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "Products",
            "KeySchema": [
                {"AttributeName": "productId", "KeyType": "HASH"},
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
    )


def test_audit_trail_table():
    """Verify AuditTrail table has correct key schema and billing mode."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")
    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "AuditTrail",
            "KeySchema": [
                {"AttributeName": "scenarioId", "KeyType": "HASH"},
                {"AttributeName": "timestamp#ruleId", "KeyType": "RANGE"},
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
    )


def test_approvals_table():
    """Verify Approvals table has correct key schema and billing mode."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")
    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "Approvals",
            "KeySchema": [
                {"AttributeName": "scenarioId", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
    )


def test_mcp_server_lambda_functions_created():
    """Verify all 4 MCP Server Lambda functions are created."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")
    template = Template.from_stack(stack)

    for name in [
        "rdp-mcp-competitor-api",
        "rdp-mcp-erp-pos",
        "rdp-mcp-market-signals",
        "rdp-mcp-cost-finance",
    ]:
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {"FunctionName": name},
        )


def test_mcp_server_lambda_runtime_and_config():
    """Verify MCP Server Lambdas use Python 3.12, 256 MB memory, 30s timeout."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")
    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Runtime": "python3.12",
            "MemorySize": 256,
            "Timeout": 30,
        },
    )


def test_cognito_user_pool_created():
    """Verify Cognito User Pool is created with email sign-in and security hardening."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")
    template = Template.from_stack(stack)

    template.resource_count_is("AWS::Cognito::UserPool", 1)
    template.has_resource_properties(
        "AWS::Cognito::UserPool",
        {
            "UserPoolName": "retail-pricing-user-pool",
            "UsernameAttributes": ["email"],
            "AutoVerifiedAttributes": ["email"],
            "Policies": {
                "PasswordPolicy": {
                    "MinimumLength": 12,
                    "RequireLowercase": True,
                    "RequireUppercase": True,
                    "RequireNumbers": True,
                    "RequireSymbols": True,
                },
            },
            "MfaConfiguration": "ON",
            "EnabledMfas": ["SOFTWARE_TOKEN_MFA"],
        },
    )


def test_cognito_user_pool_client_created():
    """Verify Cognito App Client is created for Dashboard authentication."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")
    template = Template.from_stack(stack)

    template.resource_count_is("AWS::Cognito::UserPoolClient", 1)
    template.has_resource_properties(
        "AWS::Cognito::UserPoolClient",
        {
            "ClientName": "retail-pricing-dashboard-client",
            "ExplicitAuthFlows": Match.array_with(
                [
                    "ALLOW_USER_PASSWORD_AUTH",
                    "ALLOW_USER_SRP_AUTH",
                    "ALLOW_REFRESH_TOKEN_AUTH",
                ]
            ),
        },
    )


def test_cognito_exposes_properties():
    """Verify the Cognito construct exposes user_pool and user_pool_client properties."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")

    assert stack.cognito.user_pool is not None
    assert stack.cognito.user_pool_client is not None


# --- API Handler Lambda Tests ---


def test_api_handler_lambda_functions_created():
    """Verify all 6 API handler Lambda functions are created."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")
    template = Template.from_stack(stack)

    for name in [
        "rdp-api-pricing-cycles",
        "rdp-api-scenarios",
        "rdp-api-approvals",
        "rdp-api-agents-status",
        "rdp-api-monitoring",
        "rdp-api-products",
    ]:
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {"FunctionName": name},
        )


def test_api_handler_lambda_runtime():
    """Verify API handler Lambdas use Python 3.12."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")
    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "rdp-api-pricing-cycles",
            "Runtime": "python3.12",
            "MemorySize": 256,
            "Timeout": 300,
        },
    )


def test_api_gateway_rest_api_created():
    """Verify API Gateway REST API is created."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")
    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::ApiGateway::RestApi",
        {
            "Name": "retail-dynamic-pricing-api",
        },
    )


def test_api_gateway_cognito_authorizer():
    """Verify Cognito authorizer is configured on API Gateway."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")
    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::ApiGateway::Authorizer",
        {
            "Name": "retail-pricing-cognito-authorizer",
            "Type": "COGNITO_USER_POOLS",
        },
    )


def test_api_handler_has_dynamodb_environment_vars():
    """Verify pricing cycles handler has DynamoDB table name env vars."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")
    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "rdp-api-pricing-cycles",
            "Environment": {
                "Variables": Match.object_like({
                    "PRICING_CYCLES_TABLE": Match.any_value(),
                    "PRICING_SCENARIOS_TABLE": Match.any_value(),
                }),
            },
        },
    )


def test_api_handler_has_agentcore_permissions():
    """Verify API handlers that invoke AgentCore have bedrock permissions."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")
    template = Template.from_stack(stack)

    # Verify IAM policy with bedrock/agentcore permissions exists
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with([
                    Match.object_like({
                        "Action": [
                            "bedrock:InvokeModel",
                            "bedrock:InvokeModelWithResponseStream",
                            "bedrock-agentcore:InvokeAgentRuntime",
                            "bedrock-agentcore:InvokeAgentRuntimeForUser",
                        ],
                        "Effect": "Allow",
                    }),
                ]),
            },
        },
    )


def test_api_gateway_has_products_endpoint():
    """Verify products endpoint exists without auth (public)."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")
    template = Template.from_stack(stack)

    # Verify at least one method exists without authorization
    template.has_resource_properties(
        "AWS::ApiGateway::Method",
        {
            "HttpMethod": "GET",
            "AuthorizationType": "NONE",
        },
    )


def test_api_handlers_construct_exposes_api():
    """Verify the ApiHandlers construct exposes the REST API."""
    app = cdk.App()
    stack = RetailDynamicPricingStack(app, "TestStack")

    assert stack.api_handlers.api is not None
    assert stack.api_handlers.pricing_cycles_fn is not None
    assert stack.api_handlers.products_fn is not None
