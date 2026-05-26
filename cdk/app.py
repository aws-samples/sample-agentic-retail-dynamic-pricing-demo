#!/usr/bin/env python3
"""CDK application entry point for Retail Dynamic Pricing system."""

import sys
from pathlib import Path

# Add the cdk directory to the Python path so stacks module is importable
sys.path.insert(0, str(Path(__file__).parent))

import aws_cdk as cdk

from stacks.pricing_stack import RetailDynamicPricingStack

app = cdk.App()

RetailDynamicPricingStack(
    app,
    "RetailDynamicPricing",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1",
    ),
    description="Retail Dynamic Pricing System - MVP Demo",
)

app.synth()
