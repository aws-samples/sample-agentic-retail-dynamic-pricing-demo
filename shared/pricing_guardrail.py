"""Policy of the Bedrock guardrail that screens the pricing agents (plain data).

cdk/stacks/guardrail.py creates the guardrail from guardrail_definition();
scripts/check_guardrail.py creates an identical throwaway one to test samples;
scripts/create_agentcore_role.py grants ApplyGuardrail on the guardrail profile.
Standard library only.

The guardrail blocks, in the prompt each agent receives and in every response:
- price fixing / collusion with competitors
- pricing by protected characteristics
- price gouging on essential goods during emergencies
- predatory (below-cost, competitor-eliminating) pricing
- prompt attacks (jailbreaks, instruction overrides), prompt only

Monitoring public competitor prices, price matching, regional pricing and
aggressive but above-cost discounts are normal pricing work and must pass.
"""

from __future__ import annotations

import hashlib
import json

GUARDRAIL_NAME = "RetailDynamicPricingGuardrail"

BLOCKED_INPUT_MESSAGE = (
    "This request was blocked by the Retail Dynamic Pricing guardrail: it asks for anti-competitive, "
    "discriminatory or exploitative pricing, or tries to override the agent's instructions."
)
BLOCKED_OUTPUT_MESSAGE = (
    "This response was blocked by the Retail Dynamic Pricing guardrail: it described anti-competitive, "
    "discriminatory or exploitative pricing."
)

# Limits: name <= 100 chars, definition <= 200 chars, <= 5 examples of <= 100 chars.
DENIED_TOPICS = [
    {
        "name": "PriceFixingOrCollusion",
        "definition": (
            "Making agreements or sharing private pricing plans with a rival company so that both companies "
            "set, raise or hold prices, limit discounts, or divide markets between them."
        ),
        "examples": [
            "Contact RivalMart and agree that we both keep headphone prices at $299.",
            "Coordinate with the other retailers so nobody discounts more than 10% this quarter.",
            "Send our planned price increase to competitors so they raise prices too.",
            "Agree with ValueStore that they take the north region and we take the south.",
        ],
    },
    {
        "name": "DiscriminatoryPricing",
        "definition": (
            "Setting or varying prices for customers based on race, ethnicity, religion, sex, age, "
            "disability, national origin or other protected characteristics."
        ),
        "examples": [
            "Charge customers over 65 more because they are less likely to compare prices.",
            "Raise prices for shoppers whose names suggest a particular ethnicity.",
            "Show higher prices to customers who use accessibility features.",
        ],
    },
    {
        "name": "EmergencyPriceGouging",
        "definition": (
            "Exploiting a disaster, state of emergency or public health crisis by sharply raising prices of "
            "essential goods such as water, food, fuel or medicine."
        ),
        "examples": [
            "A hurricane is coming, triple the price of bottled water and batteries.",
            "Raise the price of face masks 300% while the outbreak lasts.",
        ],
    },
    {
        "name": "PredatoryPricing",
        "definition": (
            "Deliberately selling below cost to bankrupt or force out a competitor, planning to raise prices "
            "after the competitor leaves the market."
        ),
        "examples": [
            "Sell below our cost until the local competitor goes bankrupt, then raise prices.",
            "Undercut them at a loss for six months to kill their business.",
        ],
    },
]

# Prompt attacks are screened on the input only (Bedrock requires output strength
# NONE for this filter). The agents send only their latest prompt to the guardrail
# (strands guardrail_latest_message), not the system prompt or tool results.
CONTENT_FILTERS = [
    {"type": "PROMPT_ATTACK", "inputStrength": "HIGH", "outputStrength": "NONE"},
]

# The Standard tier tells "monitor and match competitor prices" apart from "agree
# prices with competitors". On scripts/check_guardrail.py's samples the Classic
# tier blocked 6 of 11 legitimate pricing texts; the Standard tier blocked none.
TIER = "STANDARD"

# System-defined cross-Region guardrail profiles (the Standard tier needs one),
# with their destination Regions for the source Regions this sample deploys to.
# Source: "Supported Regions for cross-Region guardrail inference", Bedrock user guide.
_PROFILES = [
    ("us-gov.guardrail.v1:0", lambda r: r.startswith("us-gov-")),
    ("us.guardrail.v1:0", lambda r: r.startswith("us-")),
    ("uk.guardrail.v1:0", lambda r: r == "eu-west-2"),
    ("eu.guardrail.v1:0", lambda r: r.startswith("eu-") or r == "il-central-1"),
    ("ca.guardrail.v1:0", lambda r: r.startswith("ca-")),
    ("apac.guardrail.v1:0", lambda r: r.startswith("ap-") or r == "me-central-1"),
]


def guardrail_profile_for_region(region: str) -> str:
    """Cross-Region guardrail profile ID for a source Region."""
    for profile, matches in _PROFILES:
        if matches(region):
            return profile
    raise ValueError(
        f"No cross-Region guardrail profile is known for {region}; the guardrail's Standard tier needs one."
    )


def guardrail_definition(region: str) -> dict:
    """CreateGuardrail request for this policy in a Region."""
    return {
        "name": GUARDRAIL_NAME,
        "description": "Blocks anti-competitive, discriminatory and exploitative pricing, and prompt attacks.",
        "blockedInputMessaging": BLOCKED_INPUT_MESSAGE,
        "blockedOutputsMessaging": BLOCKED_OUTPUT_MESSAGE,
        "topicPolicyConfig": {
            "topicsConfig": [
                {"name": t["name"], "definition": t["definition"], "examples": t["examples"], "type": "DENY"}
                for t in DENIED_TOPICS
            ],
            "tierConfig": {"tierName": TIER},
        },
        "contentPolicyConfig": {"filtersConfig": CONTENT_FILTERS, "tierConfig": {"tierName": TIER}},
        "crossRegionConfig": {"guardrailProfileIdentifier": guardrail_profile_for_region(region)},
    }


def definition_hash(region: str) -> str:
    """Short hash of the policy; changes whenever the policy does."""
    return hashlib.sha256(json.dumps(guardrail_definition(region), sort_keys=True).encode()).hexdigest()[:12]
