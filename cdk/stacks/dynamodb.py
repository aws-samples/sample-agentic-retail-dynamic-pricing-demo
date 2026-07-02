"""DynamoDB table definitions for the Retail Dynamic Pricing system."""

from constructs import Construct
import aws_cdk as cdk
import aws_cdk.aws_dynamodb as dynamodb
import aws_cdk.aws_kms as kms


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

        # Security: Optionally use KMS CMK for sensitive table encryption.
        # Enable with: cdk deploy --context use_cmk_encryption=true
        # WARNING: Switching existing tables from AWS_MANAGED to CUSTOMER_MANAGED
        # causes table REPLACEMENT (data loss). Only use on fresh deployments.
        use_cmk = self.node.try_get_context("use_cmk_encryption") or False

        if use_cmk:
            self.pricing_data_key = kms.Key(
                self,
                "PricingDataKey",
                description="CMK for encrypting sensitive pricing data at rest",
                enable_key_rotation=True,
                removal_policy=cdk.RemovalPolicy.RETAIN,
            )
            sensitive_encryption = dynamodb.TableEncryption.CUSTOMER_MANAGED
            sensitive_encryption_key = self.pricing_data_key
        else:
            self.pricing_data_key = None
            sensitive_encryption = dynamodb.TableEncryption.AWS_MANAGED
            sensitive_encryption_key = None

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
            encryption=sensitive_encryption,
            encryption_key=sensitive_encryption_key,
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
            # Security: Enable streams for change detection and alerting
            # on unauthorized out-of-band price modifications
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
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
            encryption=sensitive_encryption,
            encryption_key=sensitive_encryption_key,
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
            encryption=sensitive_encryption,
            encryption_key=sensitive_encryption_key,
            point_in_time_recovery=True,
        )
