"""CDK construct for S3 + CloudFront hosting of frontend applications.

Both frontends (Dashboard and Storefront) are static Vite/React builds served
from private S3 buckets behind CloudFront distributions (origin access identity).
The build artifacts are uploaded to the buckets by deploy.sh (`aws s3 sync`).
"""

from constructs import Construct
import aws_cdk as cdk
import aws_cdk.aws_cloudfront as cloudfront
import aws_cdk.aws_cloudfront_origins as origins
import aws_cdk.aws_s3 as s3


class HostingConstruct(Construct):
    """Hosting infrastructure for Dashboard and Storefront frontend apps.

    Serves both frontend applications from S3 buckets behind CloudFront
    distributions (CDN delivery over HTTPS, origin locked down via OAI).

    - Dashboard: React/TS app authenticated via Cognito
    - Storefront: React/TS public app (no auth)
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- Access Logging Bucket ---
        self.access_logs_bucket = s3.Bucket(
            self,
            "AccessLogsBucket",
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_PREFERRED,
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=cdk.Duration.days(90),
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=cdk.Duration.days(30),
                        ),
                    ],
                ),
            ],
        )

        # --- Security Response Headers Policy ---
        # Applied to all CloudFront distributions to set CSP, HSTS,
        # X-Frame-Options, X-Content-Type-Options, and Referrer-Policy.
        # Satisfies BSC AWS-26 (Set Secure HTTP Headers for Websites).
        security_headers_policy = cloudfront.ResponseHeadersPolicy(
            self,
            "SecurityHeadersPolicy",
            response_headers_policy_name="RetailPricing-SecurityHeaders",
            comment="Security headers for Retail Dynamic Pricing Demo",
            security_headers_behavior=cloudfront.ResponseSecurityHeadersBehavior(
                content_security_policy=cloudfront.ResponseHeadersContentSecurityPolicy(
                    content_security_policy=(
                        "default-src 'self'; "
                        "script-src 'self'; "
                        "style-src 'self' 'unsafe-inline'; "
                        "img-src 'self' data: https://images.unsplash.com; "
                        "font-src 'self'; "
                        "connect-src 'self' https://*.amazonaws.com https://*.amazoncognito.com; "
                        "frame-ancestors 'none'; "
                        "base-uri 'self'; "
                        "form-action 'self'"
                    ),
                    override=True,
                ),
                content_type_options=cloudfront.ResponseHeadersContentTypeOptions(
                    override=True,
                ),
                frame_options=cloudfront.ResponseHeadersFrameOptions(
                    frame_option=cloudfront.HeadersFrameOption.DENY,
                    override=True,
                ),
                referrer_policy=cloudfront.ResponseHeadersReferrerPolicy(
                    referrer_policy=cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN,
                    override=True,
                ),
                strict_transport_security=cloudfront.ResponseHeadersStrictTransportSecurity(
                    access_control_max_age=cdk.Duration.seconds(63072000),
                    include_subdomains=True,
                    preload=True,
                    override=True,
                ),
            ),
        )

        # --- CloudFront Distribution for Dashboard ---
        self.dashboard_bucket = s3.Bucket(
            self,
            "DashboardBucket",
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            server_access_logs_bucket=self.access_logs_bucket,
            server_access_logs_prefix="s3-dashboard/",
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
                response_headers_policy=security_headers_policy,
            ),
            default_root_object="index.html",
            log_bucket=self.access_logs_bucket,
            log_file_prefix="cloudfront-dashboard/",
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
            versioned=True,
            server_access_logs_bucket=self.access_logs_bucket,
            server_access_logs_prefix="s3-storefront/",
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
                response_headers_policy=security_headers_policy,
            ),
            default_root_object="index.html",
            log_bucket=self.access_logs_bucket,
            log_file_prefix="cloudfront-storefront/",
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
            "DashboardCloudFrontUrl",
            value=cdk.Fn.sub(
                "https://${Domain}",
                {"Domain": self.dashboard_distribution.distribution_domain_name},
            ),
            description="Dashboard CloudFront distribution URL",
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
