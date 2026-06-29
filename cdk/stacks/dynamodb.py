"""DynamoDB table definitions for the Retail Dynamic Pricing system."""

from constructs import Construct
import aws_cdk as cdk
import aws_cdk.aws_dynamodb as dynamodb


class DynamoDBTables(Construct):
    """Construct that defines all DynamoDB tables for the pricing system.

    Tables:
    - PricingCycles: Stores pricing cycle metadata and agent statuses
    - PricingScenarios: Stores generated pricing scenarios per cycle
    - Products: Product catalog with current pricing
    - AuditTrail: Guardrail evaluation audit records
    - Approvals: Approval workflow actions
    """

    def __init__(self, scope: Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        self.pricing_cycles_table = dynamodb.Table(
            self,
            "PricingCyclesTable",
            table_name="PricingCycles",
            partition_key=dynamodb.Attribute(
                name="cycleId",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="status",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            time_to_live_attribute="ttl",
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            point_in_time_recovery=True,
        )

        self.pricing_scenarios_table = dynamodb.Table(
            self,
            "PricingScenariosTable",
            table_name="PricingScenarios",
            partition_key=dynamodb.Attribute(
                name="cycleId",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="scenarioId",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            point_in_time_recovery=True,
        )

        self.products_table = dynamodb.Table(
            self,
            "ProductsTable",
            table_name="Products",
            partition_key=dynamodb.Attribute(
                name="productId",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            point_in_time_recovery=True,
        )

        self.audit_trail_table = dynamodb.Table(
            self,
            "AuditTrailTable",
            table_name="AuditTrail",
            partition_key=dynamodb.Attribute(
                name="scenarioId",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp#ruleId",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            point_in_time_recovery=True,
        )

        self.approvals_table = dynamodb.Table(
            self,
            "ApprovalsTable",
            table_name="Approvals",
            partition_key=dynamodb.Attribute(
                name="scenarioId",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            point_in_time_recovery=True,
        )
