"""Main CDK stack for the Retail Dynamic Pricing system."""

from constructs import Construct
import aws_cdk as cdk
from aws_cdk import aws_budgets as budgets
from aws_cdk import aws_cloudwatch as cloudwatch

from stacks.cognito import CognitoAuth
from stacks.dynamodb import DynamoDBTables
from stacks.mcp_servers import McpServersConstruct
from stacks.hosting import HostingConstruct
from stacks.api_handlers import ApiHandlersConstruct


class RetailDynamicPricingStack(cdk.Stack):
    """Root stack for the Retail Dynamic Pricing system.

    This stack contains all constructs for DynamoDB tables, Cognito,
    API Gateway, Lambda functions, CloudFront, and Amplify hosting.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        cdk.Tags.of(self).add("Project", "RetailDynamicPricing")
        cdk.Tags.of(self).add("Environment", "demo")
        cdk.Tags.of(self).add("ManagedBy", "CDK")

        # DynamoDB tables
        self.dynamodb = DynamoDBTables(self, "DynamoDB")

        # Cognito User Pool and App Client for Dashboard authentication
        self.cognito = CognitoAuth(self, "CognitoAuth")

        # MCP Server Lambda functions
        self.mcp_servers = McpServersConstruct(self, "McpServers")

        # Hosting: CloudFront + Amplify for Dashboard and Storefront
        self.hosting = HostingConstruct(self, "Hosting")

        # Update Cognito callback URLs with the actual CloudFront domain
        # (fixes redirect_mismatch on fresh deployments)
        dashboard_url = cdk.Fn.sub(
            "https://${Domain}/callback",
            {"Domain": self.hosting.dashboard_distribution.distribution_domain_name},
        )
        dashboard_logout = cdk.Fn.sub(
            "https://${Domain}",
            {"Domain": self.hosting.dashboard_distribution.distribution_domain_name},
        )
        cfn_client = self.cognito.user_pool_client.node.default_child
        cfn_client.add_property_override(
            "CallbackURLs",
            ["https://localhost:5173/callback", "http://localhost:5173/callback", dashboard_url],
        )
        cfn_client.add_property_override(
            "LogoutURLs",
            ["https://localhost:5173", "http://localhost:5173", dashboard_logout],
        )

        # API Gateway Lambda handlers
        self.api_handlers = ApiHandlersConstruct(
            self,
            "ApiHandlers",
            dynamodb_tables=self.dynamodb,
            cognito_auth=self.cognito,
            hosting=self.hosting,
        )

        # --- AWS Budget Alarm for Bedrock Spend ---
        # Triggers notification when monthly Bedrock spend exceeds $50
        budgets.CfnBudget(
            self,
            "BedrockSpendBudget",
            budget=budgets.CfnBudget.BudgetDataProperty(
                budget_name="RetailDynamicPricing-BedrockSpend",
                budget_type="COST",
                time_unit="MONTHLY",
                budget_limit=budgets.CfnBudget.SpendProperty(
                    amount=50,
                    unit="USD",
                ),
                cost_filters={
                    "Service": ["Amazon Bedrock"],
                },
            ),
            notifications_with_subscribers=[
                budgets.CfnBudget.NotificationWithSubscribersProperty(
                    notification=budgets.CfnBudget.NotificationProperty(
                        comparison_operator="GREATER_THAN",
                        notification_type="ACTUAL",
                        threshold=80,
                        threshold_type="PERCENTAGE",
                    ),
                    subscribers=[
                        budgets.CfnBudget.SubscriberProperty(
                            address="admin@example.com",
                            subscription_type="EMAIL",
                        ),
                    ],
                ),
            ],
        )

        # --- CloudWatch Operational Dashboard ---
        # Provides pre-built monitoring for Lambda functions, DynamoDB,
        # and API Gateway performance metrics.
        dashboard = cloudwatch.Dashboard(
            self,
            "OperationalDashboard",
            dashboard_name="RetailDynamicPricing-Operations",
        )

        # Lambda metrics (pricing cycles handler — the most critical function)
        pricing_fn_name = "rdp-api-pricing-cycles"

        dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown="# Retail Dynamic Pricing — Operational Metrics\n"
                "Real-time monitoring of the pricing pipeline components.",
                width=24,
                height=2,
            ),
        )

        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Lambda Invocations (All Handlers)",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/Lambda",
                        metric_name="Invocations",
                        dimensions_map={"FunctionName": pricing_fn_name},
                        statistic="Sum",
                        period=cdk.Duration.minutes(5),
                    ),
                    cloudwatch.Metric(
                        namespace="AWS/Lambda",
                        metric_name="Invocations",
                        dimensions_map={"FunctionName": "rdp-api-approvals"},
                        statistic="Sum",
                        period=cdk.Duration.minutes(5),
                    ),
                    cloudwatch.Metric(
                        namespace="AWS/Lambda",
                        metric_name="Invocations",
                        dimensions_map={"FunctionName": "rdp-api-products"},
                        statistic="Sum",
                        period=cdk.Duration.minutes(5),
                    ),
                ],
                width=12,
                height=6,
            ),
            cloudwatch.GraphWidget(
                title="Lambda Errors",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/Lambda",
                        metric_name="Errors",
                        dimensions_map={"FunctionName": pricing_fn_name},
                        statistic="Sum",
                        period=cdk.Duration.minutes(5),
                    ),
                ],
                width=6,
                height=6,
            ),
            cloudwatch.GraphWidget(
                title="Lambda Duration (p90)",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/Lambda",
                        metric_name="Duration",
                        dimensions_map={"FunctionName": pricing_fn_name},
                        statistic="p90",
                        period=cdk.Duration.minutes(5),
                    ),
                ],
                width=6,
                height=6,
            ),
        )

        # DynamoDB metrics
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="DynamoDB Read/Write Capacity (Products)",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/DynamoDB",
                        metric_name="ConsumedReadCapacityUnits",
                        dimensions_map={"TableName": "Products"},
                        statistic="Sum",
                        period=cdk.Duration.minutes(5),
                    ),
                    cloudwatch.Metric(
                        namespace="AWS/DynamoDB",
                        metric_name="ConsumedWriteCapacityUnits",
                        dimensions_map={"TableName": "Products"},
                        statistic="Sum",
                        period=cdk.Duration.minutes(5),
                    ),
                ],
                width=12,
                height=6,
            ),
            cloudwatch.GraphWidget(
                title="DynamoDB Throttled Requests",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/DynamoDB",
                        metric_name="ThrottledRequests",
                        dimensions_map={"TableName": "PricingCycles"},
                        statistic="Sum",
                        period=cdk.Duration.minutes(5),
                    ),
                    cloudwatch.Metric(
                        namespace="AWS/DynamoDB",
                        metric_name="ThrottledRequests",
                        dimensions_map={"TableName": "PricingScenarios"},
                        statistic="Sum",
                        period=cdk.Duration.minutes(5),
                    ),
                ],
                width=12,
                height=6,
            ),
        )

        # API Gateway metrics
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="API Gateway Latency (p50/p90/p99)",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/ApiGateway",
                        metric_name="Latency",
                        dimensions_map={"ApiName": "retail-dynamic-pricing-api"},
                        statistic="p50",
                        period=cdk.Duration.minutes(5),
                    ),
                    cloudwatch.Metric(
                        namespace="AWS/ApiGateway",
                        metric_name="Latency",
                        dimensions_map={"ApiName": "retail-dynamic-pricing-api"},
                        statistic="p90",
                        period=cdk.Duration.minutes(5),
                    ),
                    cloudwatch.Metric(
                        namespace="AWS/ApiGateway",
                        metric_name="Latency",
                        dimensions_map={"ApiName": "retail-dynamic-pricing-api"},
                        statistic="p99",
                        period=cdk.Duration.minutes(5),
                    ),
                ],
                width=12,
                height=6,
            ),
            cloudwatch.GraphWidget(
                title="API Gateway 4xx/5xx Errors",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/ApiGateway",
                        metric_name="4XXError",
                        dimensions_map={"ApiName": "retail-dynamic-pricing-api"},
                        statistic="Sum",
                        period=cdk.Duration.minutes(5),
                    ),
                    cloudwatch.Metric(
                        namespace="AWS/ApiGateway",
                        metric_name="5XXError",
                        dimensions_map={"ApiName": "retail-dynamic-pricing-api"},
                        statistic="Sum",
                        period=cdk.Duration.minutes(5),
                    ),
                ],
                width=12,
                height=6,
            ),
        )
