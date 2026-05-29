"""Cognito User Pool and App Client construct for Dashboard authentication."""

from constructs import Construct
import aws_cdk as cdk
import aws_cdk.aws_cognito as cognito


class CognitoAuth(Construct):
    """Cognito User Pool and App Client for Dashboard authentication.

    Creates a User Pool with email-based sign-in and an App Client
    configured for JWT token generation, suitable for API Gateway
    Cognito authorizer integration.
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
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # Create App Client for Dashboard authentication
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
                    implicit_code_grant=True,
                ),
                scopes=[
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.PROFILE,
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

    @property
    def user_pool(self) -> cognito.UserPool:
        """The Cognito User Pool for API Gateway authorizer integration."""
        return self._user_pool

    @property
    def user_pool_client(self) -> cognito.UserPoolClient:
        """The Cognito App Client for Dashboard authentication."""
        return self._user_pool_client
