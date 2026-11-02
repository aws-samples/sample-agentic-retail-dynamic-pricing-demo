"""Amazon Bedrock guardrail for the pricing agents.

The five model-backed agents attach this guardrail to every Converse call
(backend/agents/agentcore/guardrail_config.py). The policy itself (denied topics,
prompt-attack filter, tier, cross-Region profile) lives in
shared/pricing_guardrail.py, so scripts/check_guardrail.py can test an identical
guardrail without a deploy.

A change to the policy creates a new guardrail version (the version description
carries the policy hash); scripts/deploy_agentcore.py attaches the version from
the BedrockGuardrailId / BedrockGuardrailVersion stack outputs.
"""

from __future__ import annotations

import os

import aws_cdk as cdk
from aws_cdk import aws_bedrock as bedrock
from constructs import Construct

from shared.pricing_guardrail import definition_hash, guardrail_definition


class PricingGuardrail(Construct):
    """The guardrail, a published version of it, and stack outputs with both."""

    def __init__(self, scope: Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)
        region = cdk.Stack.of(self).region
        if cdk.Token.is_unresolved(region):
            # cdk/app.py always sets a Region; environment-agnostic synths (tests) fall back.
            region = os.environ.get("CDK_DEFAULT_REGION") or "us-east-1"
            cdk.Annotations.of(self).add_warning(
                f"Stack has no concrete Region; using the {region} guardrail profile.")
        d = guardrail_definition(region)
        profile_arn = (
            f"arn:{cdk.Aws.PARTITION}:bedrock:{region}:{cdk.Aws.ACCOUNT_ID}:guardrail-profile/"
            f"{d['crossRegionConfig']['guardrailProfileIdentifier']}"
        )

        self.guardrail = bedrock.CfnGuardrail(
            self,
            "Guardrail",
            name=d["name"],
            description=d["description"],
            blocked_input_messaging=d["blockedInputMessaging"],
            blocked_outputs_messaging=d["blockedOutputsMessaging"],
            topic_policy_config=bedrock.CfnGuardrail.TopicPolicyConfigProperty(
                topics_config=[
                    bedrock.CfnGuardrail.TopicConfigProperty(
                        name=t["name"], definition=t["definition"], examples=t["examples"], type=t["type"]
                    )
                    for t in d["topicPolicyConfig"]["topicsConfig"]
                ],
                topics_tier_config=bedrock.CfnGuardrail.TopicsTierConfigProperty(
                    tier_name=d["topicPolicyConfig"]["tierConfig"]["tierName"]
                ),
            ),
            content_policy_config=bedrock.CfnGuardrail.ContentPolicyConfigProperty(
                filters_config=[
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        type=f["type"], input_strength=f["inputStrength"], output_strength=f["outputStrength"]
                    )
                    for f in d["contentPolicyConfig"]["filtersConfig"]
                ],
                content_filters_tier_config=bedrock.CfnGuardrail.ContentFiltersTierConfigProperty(
                    tier_name=d["contentPolicyConfig"]["tierConfig"]["tierName"]
                ),
            ),
            cross_region_config=bedrock.CfnGuardrail.GuardrailCrossRegionConfigProperty(
                guardrail_profile_arn=profile_arn
            ),
        )

        # A version is an immutable snapshot of the guardrail. The policy hash in the
        # description replaces the version (creating a new one) whenever the policy
        # changes, so the agents never keep running on a stale snapshot.
        self.version = bedrock.CfnGuardrailVersion(
            self,
            "Version",
            guardrail_identifier=self.guardrail.attr_guardrail_id,
            description=f"{d['name']} policy {definition_hash(region)}",
        )

        cdk.CfnOutput(scope, "BedrockGuardrailId", value=self.guardrail.attr_guardrail_id,
                      description="Bedrock guardrail attached to the pricing agents")
        cdk.CfnOutput(scope, "BedrockGuardrailVersion", value=self.version.attr_version,
                      description="Published guardrail version the agents use")
