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

        # API Gateway Lambda handlers
        self.api_handlers = ApiHandlersConstruct(
            self,
            "ApiHandlers",
            dynamodb_tables=self.dynamodb,
            cognito_auth=self.cognito,
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
