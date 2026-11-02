"""The Bedrock guardrail created by the stack, and how it reaches the agents.

The policy is plain data (shared/pricing_guardrail.py); the live classification
of legitimate vs harmful samples is checked by scripts/check_guardrail.py
(ApplyGuardrail), which these tests keep honest structurally.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from shared import pricing_guardrail as pg

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import check_guardrail  # noqa: E402
import verify_deployment  # noqa: E402

REGION = "us-east-1"


@pytest.fixture(scope="module")
def template():
    import aws_cdk as cdk
    from aws_cdk.assertions import Template
    from stacks.pricing_stack import RetailDynamicPricingStack

    app = cdk.App(context={"alertEmail": "ops@example.com"})
    stack = RetailDynamicPricingStack(app, "GuardrailTestStack", env=cdk.Environment(region=REGION))
    return Template.from_stack(stack)


class TestPolicy:
    def test_topics_fit_the_api_limits(self):
        for topic in pg.DENIED_TOPICS:
            assert len(topic["name"]) <= 100
            assert len(topic["definition"]) <= 200, topic["name"]
            assert len(topic["examples"]) <= 5
            assert all(len(example) <= 100 for example in topic["examples"])

    def test_the_harms_the_readme_promises_are_covered(self):
        names = {t["name"] for t in pg.DENIED_TOPICS}
        assert {"PriceFixingOrCollusion", "DiscriminatoryPricing", "EmergencyPriceGouging", "PredatoryPricing"} <= names
        assert {"type": "PROMPT_ATTACK", "inputStrength": "HIGH", "outputStrength": "NONE"} in pg.CONTENT_FILTERS

    def test_standard_tier_with_a_cross_region_profile(self):
        definition = pg.guardrail_definition(REGION)
        assert definition["topicPolicyConfig"]["tierConfig"] == {"tierName": "STANDARD"}
        assert definition["contentPolicyConfig"]["tierConfig"] == {"tierName": "STANDARD"}
        assert definition["crossRegionConfig"] == {"guardrailProfileIdentifier": "us.guardrail.v1:0"}

    @pytest.mark.parametrize("region,profile", [
        ("us-east-1", "us.guardrail.v1:0"), ("us-west-2", "us.guardrail.v1:0"),
        ("us-gov-west-1", "us-gov.guardrail.v1:0"), ("eu-central-1", "eu.guardrail.v1:0"),
        ("eu-west-2", "uk.guardrail.v1:0"), ("ap-southeast-2", "apac.guardrail.v1:0"),
        ("ca-central-1", "ca.guardrail.v1:0"),
    ])
    def test_profile_per_geography(self, region, profile):
        assert pg.guardrail_profile_for_region(region) == profile

    def test_unknown_geography_is_an_error(self):
        with pytest.raises(ValueError):
            pg.guardrail_profile_for_region("sa-east-1")

    def test_hash_changes_with_the_policy(self, monkeypatch):
        before = pg.definition_hash(REGION)
        monkeypatch.setattr(pg, "BLOCKED_INPUT_MESSAGE", "changed")
        assert pg.definition_hash(REGION) != before


class TestStack:
    def test_guardrail_matches_the_policy(self, template):
        (guardrail,) = template.find_resources("AWS::Bedrock::Guardrail").values()
        props = guardrail["Properties"]
        assert props["Name"] == pg.GUARDRAIL_NAME
        assert [t["Name"] for t in props["TopicPolicyConfig"]["TopicsConfig"]] == [t["name"] for t in pg.DENIED_TOPICS]
        assert props["TopicPolicyConfig"]["TopicsTierConfig"] == {"TierName": "STANDARD"}
        assert props["ContentPolicyConfig"]["ContentFiltersTierConfig"] == {"TierName": "STANDARD"}
        assert "us.guardrail.v1:0" in str(props["CrossRegionConfig"]["GuardrailProfileArn"])

    def test_a_published_version_is_exported(self, template):
        (version,) = template.find_resources("AWS::Bedrock::GuardrailVersion").values()
        assert pg.definition_hash(REGION) in version["Properties"]["Description"]
        outputs = template.to_json()["Outputs"]
        assert {"BedrockGuardrailId", "BedrockGuardrailVersion"} <= set(outputs)


class TestCheckScript:
    def test_samples_cover_both_directions(self):
        for samples in (check_guardrail.ALLOWED, check_guardrail.BLOCKED):
            assert samples["INPUT"] and samples["OUTPUT"]

    def test_allowed_samples_include_the_words_that_used_to_trip_filters(self):
        """Competitor monitoring, price matching and the agents' own JSON keys must pass."""
        allowed = " ".join(check_guardrail.ALLOWED["INPUT"] + check_guardrail.ALLOWED["OUTPUT"])
        for phrase in ("RivalMart", "Match within 2%", "undercut", "priceTrendAnalysis", "channel_specific_guidance",
                       "abundant", "guidance", "redundancy"):
            assert phrase in allowed

    def test_check_flags_misclassification(self):
        class Runtime:
            def apply_guardrail(self, **kw):
                return {"action": "GUARDRAIL_INTERVENED", "assessments": []}

        failures = check_guardrail.check(Runtime(), "gr", "1")
        allowed_count = sum(len(v) for v in check_guardrail.ALLOWED.values())
        assert len(failures) == allowed_count  # every allowed sample was (wrongly) blocked


class TestVerifyGuardrail:
    OUTPUTS = {"BedrockGuardrailId": "gr-1", "BedrockGuardrailVersion": "2"}
    GOOD = {"BEDROCK_GUARDRAIL_ID": "gr-1", "BEDROCK_GUARDRAIL_VERSION": "2"}

    def test_all_runtimes_on_the_stack_guardrail_pass(self):
        envs = {agent: dict(self.GOOD) for agent in verify_deployment.GUARDED_RUNTIMES}
        assert verify_deployment.compare_runtime_guardrails(envs, self.OUTPUTS) == []

    def test_a_disabled_or_stale_guardrail_fails(self):
        envs = {agent: dict(self.GOOD) for agent in verify_deployment.GUARDED_RUNTIMES}
        envs["demand-forecasting"] = {"DISABLE_BEDROCK_GUARDRAILS": "true"}
        envs["market-intelligence"] = {**self.GOOD, "BEDROCK_GUARDRAIL_VERSION": "1"}
        problems = verify_deployment.compare_runtime_guardrails(envs, self.OUTPUTS)
        assert any("demand-forecasting: DISABLE_BEDROCK_GUARDRAILS=true" in p for p in problems)
        assert any("market-intelligence" in p and "v1" in p for p in problems)

    def test_a_stack_without_the_guardrail_fails(self):
        assert verify_deployment.compare_runtime_guardrails({}, {})

    def test_the_orchestrator_is_not_required_to_have_one(self):
        assert "orchestrator" not in verify_deployment.GUARDED_RUNTIMES
