"""CDK construct for CloudFront and Amplify hosting of frontend applications."""

from constructs import Construct
import aws_cdk as cdk
import aws_cdk.aws_amplify as amplify
import aws_cdk.aws_cloudfront as cloudfront
import aws_cdk.aws_cloudfront_origins as origins
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_iam as iam


class HostingConstruct(Construct):
    """Hosting infrastructure for Dashboard and Storefront frontend apps.

    Creates AWS Amplify Hosting for both frontend applications with
    CloudFront distributions for CDN delivery.

    - Dashboard: React/TS app authenticated via Cognito
    - Storefront: React/TS public app (no auth)
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- IAM Role for Amplify ---
        amplify_role = iam.Role(
            self,
            "AmplifyServiceRole",
            assumed_by=iam.ServicePrincipal("amplify.amazonaws.com"),
            description="Service role for Amplify hosting of frontend apps",
        )

        # --- Dashboard Amplify App ---
        self.dashboard_app = amplify.CfnApp(
            self,
            "DashboardApp",
            name="retail-pricing-dashboard",
            iam_service_role=amplify_role.role_arn,
            platform="WEB",
            custom_rules=[
                amplify.CfnApp.CustomRuleProperty(
                    source="</^[^.]+$|\\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json|webp)$)([^.]+$)/>",
                    target="/index.html",
                    status="200",
                ),
            ],
            environment_variables=[
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="AMPLIFY_MONOREPO_APP_ROOT",
                    value="frontend/dashboard",
                ),
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="_LIVE_UPDATES",
                    value='[{"pkg":"node","type":"nvm","version":"20"}]',
                ),
            ],
            build_spec=self._get_build_spec(),
        )

        # Dashboard main branch
        self.dashboard_branch = amplify.CfnBranch(
            self,
            "DashboardMainBranch",
            app_id=self.dashboard_app.attr_app_id,
            branch_name="main",
            stage="PRODUCTION",
            enable_auto_build=True,
        )

        # --- Storefront Amplify App ---
        self.storefront_app = amplify.CfnApp(
            self,
            "StorefrontApp",
            name="retail-pricing-storefront",
            iam_service_role=amplify_role.role_arn,
            platform="WEB",
            custom_rules=[
                amplify.CfnApp.CustomRuleProperty(
                    source="</^[^.]+$|\\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json|webp)$)([^.]+$)/>",
                    target="/index.html",
                    status="200",
                ),
            ],
            environment_variables=[
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="AMPLIFY_MONOREPO_APP_ROOT",
                    value="frontend/storefront",
                ),
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="_LIVE_UPDATES",
                    value='[{"pkg":"node","type":"nvm","version":"20"}]',
                ),
            ],
            build_spec=self._get_build_spec(),
        )

        # Storefront main branch
        self.storefront_branch = amplify.CfnBranch(
            self,
            "StorefrontMainBranch",
            app_id=self.storefront_app.attr_app_id,
            branch_name="main",
            stage="PRODUCTION",
            enable_auto_build=True,
        )

        # --- CloudFront Distribution for Dashboard ---
        self.dashboard_bucket = s3.Bucket(
            self,
            "DashboardBucket",
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )

        dashboard_oai = cloudfront.OriginAccessIdentity(
            self,
            "DashboardOAI",
            comment="OAI for Dashboard",
        )
        self.dashboard_bucket.grant_read(dashboard_oai)

        self.dashboard_distribution = cloudfront.Distribution(
            self,
            "DashboardDistribution",
            comment="Retail Dynamic Pricing Dashboard CDN",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(
                    self.dashboard_bucket,
                    origin_access_identity=dashboard_oai,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=cdk.Duration.seconds(0),
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=cdk.Duration.seconds(0),
                ),
            ],
        )

        # --- CloudFront Distribution for Storefront ---
        self.storefront_bucket = s3.Bucket(
            self,
            "StorefrontBucket",
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )

        storefront_oai = cloudfront.OriginAccessIdentity(
            self,
            "StorefrontOAI",
            comment="OAI for Storefront",
        )
        self.storefront_bucket.grant_read(storefront_oai)

        self.storefront_distribution = cloudfront.Distribution(
            self,
            "StorefrontDistribution",
            comment="Retail Dynamic Pricing Storefront CDN",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(
                    self.storefront_bucket,
                    origin_access_identity=storefront_oai,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=cdk.Duration.seconds(0),
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=cdk.Duration.seconds(0),
                ),
            ],
        )

        # --- Stack Outputs ---
        cdk.CfnOutput(
            self,
            "DashboardAmplifyAppId",
            value=self.dashboard_app.attr_app_id,
            description="Amplify App ID for Dashboard",
        )

        cdk.CfnOutput(
            self,
            "DashboardCloudFrontUrl",
            value=cdk.Fn.sub(
                "https://${Domain}",
                {"Domain": self.dashboard_distribution.distribution_domain_name},
            ),
            description="Dashboard CloudFront distribution URL",
        )

        cdk.CfnOutput(
            self,
            "StorefrontAmplifyAppId",
            value=self.storefront_app.attr_app_id,
            description="Amplify App ID for Storefront",
        )

        cdk.CfnOutput(
            self,
            "StorefrontCloudFrontUrl",
            value=cdk.Fn.sub(
                "https://${Domain}",
                {"Domain": self.storefront_distribution.distribution_domain_name},
            ),
            description="Storefront CloudFront distribution URL",
        )

    @staticmethod
    def _get_build_spec() -> str:
        """Return the Amplify build spec for a Vite React/TypeScript app."""
        return """version: 1
frontend:
  phases:
    preBuild:
      commands:
        - npm ci
    build:
      commands:
        - npm run build
  artifacts:
    baseDirectory: dist
    files:
      - '**/*'
  cache:
    paths:
      - node_modules/**/*
"""
