"""Main CDK stack for the Retail Dynamic Pricing system."""

from constructs import Construct
import aws_cdk as cdk

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
