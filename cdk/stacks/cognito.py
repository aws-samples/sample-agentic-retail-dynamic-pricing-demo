"""Cognito User Pool and App Client construct for Dashboard authentication."""

from constructs import Construct
import aws_cdk as cdk
import aws_cdk.aws_cognito as cognito


class CognitoAuth(Construct):
    """Cognito User Pool and App Client for Dashboard authentication.

    Creates a User Pool with email-based sign-in and an App Client
    configured for JWT token generation, suitable for API Gateway
    Cognito authorizer integration.

    The Cognito domain is created automatically using the account ID for
    uniqueness. Callback URLs are configured with a placeholder that must
    be updated after the CloudFront distribution is created (see post-deploy
    steps in the README).
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id)

        # Create Cognito User Pool with email sign-in
        # Self-registration disabled: only admins can create users
        self._user_pool = cognito.UserPool(
            self,
            "DashboardUserPool",
            user_pool_name="retail-pricing-user-pool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(
                    required=True,
                    mutable=True,
                ),
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            # Security: Require TOTP MFA for all users
            mfa=cognito.Mfa.REQUIRED,
            mfa_second_factor=cognito.MfaSecondFactor(
                sms=False,
                otp=True,
            ),
        )

        # Add Cognito hosted UI domain (required for OAuth login flows)
        # Uses account ID suffix for global uniqueness
        self._domain = self._user_pool.add_domain(
            "CognitoDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"retail-pricing-{cdk.Aws.ACCOUNT_ID}",
            ),
        )

        # Create App Client for Dashboard authentication
        # Callback URLs use localhost for dev; update with CloudFront URL post-deploy
        # using: aws cognito-idp update-user-pool-client --callback-urls [...]
        self._user_pool_client = self._user_pool.add_client(
            "DashboardAppClient",
            user_pool_client_name="retail-pricing-dashboard-client",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True,
                    # Implicit grant disabled for security — frontend uses
                    # authorization code flow with PKCE instead.
                    implicit_code_grant=False,
                ),
                scopes=[
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.PROFILE,
                ],
                callback_urls=[
                    "https://localhost:5173/callback",
                    "http://localhost:5173/callback",
                ],
                logout_urls=[
                    "https://localhost:5173",
                    "http://localhost:5173",
                ],
            ),
            id_token_validity=cdk.Duration.hours(1),
            access_token_validity=cdk.Duration.hours(1),
            refresh_token_validity=cdk.Duration.days(30),
            prevent_user_existence_errors=True,
        )

        # Outputs for frontend configuration
        cdk.CfnOutput(
            self,
            "UserPoolId",
            value=self._user_pool.user_pool_id,
            description="Cognito User Pool ID",
        )

        cdk.CfnOutput(
            self,
            "UserPoolClientId",
            value=self._user_pool_client.user_pool_client_id,
            description="Cognito App Client ID",
        )

        cdk.CfnOutput(
            self,
            "CognitoDomain",
            value=f"retail-pricing-{cdk.Aws.ACCOUNT_ID}.auth.{cdk.Aws.REGION}.amazoncognito.com",
            description="Cognito Hosted UI Domain",
        )

        # --- Cognito Groups for Role-Based Access ---
        # PricingAnalysts: Standard users who run pricing cycles and approve scenarios
        cognito.CfnUserPoolGroup(
            self,
            "PricingAnalystsGroup",
            user_pool_id=self._user_pool.user_pool_id,
            group_name="PricingAnalysts",
            description="Pricing analysts who run cycles and approve scenarios",
        )

        # Operations: System operators who see metrics, health, architecture, and TCO
        cognito.CfnUserPoolGroup(
            self,
            "OperationsGroup",
            user_pool_id=self._user_pool.user_pool_id,
            group_name="Operations",
            description="Operations team with access to system metrics and health",
        )

    @property
    def user_pool(self) -> cognito.UserPool:
        """The Cognito User Pool for API Gateway authorizer integration."""
        return self._user_pool

    @property
    def user_pool_client(self) -> cognito.UserPoolClient:
        """The Cognito App Client for Dashboard authentication."""
        return self._user_pool_client

    @property
    def domain_prefix(self) -> str:
        """The Cognito domain prefix for the hosted UI."""
        return f"retail-pricing-{cdk.Aws.ACCOUNT_ID}"
