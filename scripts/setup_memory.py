"""Create AgentCore Memory resource for the Retail Dynamic Pricing system.

This script provisions a memory resource with semantic and summary strategies
that agents use to persist pricing outcomes and learning across cycles.

Usage:
    python scripts/setup_memory.py [--region us-east-1]

After running, export the printed AGENTCORE_MEMORY_ID as an environment variable
for agent containers.
"""

from __future__ import annotations

import argparse
import sys

from bedrock_agentcore.memory import MemoryClient


def setup_memory(region: str = "us-east-1") -> str:
    """Create the AgentCore Memory resource.

    Idempotent — if memory with the same name already exists, returns the
    existing memory ID instead of failing.

    Args:
        region: AWS region to create the memory resource in.

    Returns:
        The memory resource ID.
    """
    client = MemoryClient(region_name=region)

    print(f"Creating AgentCore Memory in {region}...")

    # Check if memory already exists
    try:
        existing_memories = client.list_memories()
        for mem in existing_memories.get("memories", []):
            if mem.get("name") == "RetailDynamicPricingMemory":
                memory_id = mem.get("id")
                print(f"  Memory already exists: {memory_id}")
                print(f"\nExport this for your agent containers:")
                print(f"  export AGENTCORE_MEMORY_ID={memory_id}")
                return memory_id
    except Exception:
        pass  # list_memories may not be available; fall through to create

    memory = client.create_memory_and_wait(
        name="RetailDynamicPricingMemory",
        description=(
            "Memory for retail dynamic pricing agents - stores pricing outcomes, "
            "competitive intelligence, demand patterns, and learning across cycles."
        ),
        strategies=[
            {
                "semanticMemoryStrategy": {
                    "name": "PricingOutcomes",
                    "namespaceTemplates": ["/pricing/{actorId}/{sessionId}/"],
                }
            },
            {
                "summaryMemoryStrategy": {
                    "name": "CycleSummarizer",
                    "namespaceTemplates": ["/summaries/{actorId}/{sessionId}/"],
                }
            },
        ],
    )

    memory_id = memory.get("id")
    print(f"\nMemory created successfully!")
    print(f"  Memory ID: {memory_id}")
    print(f"  Region:    {region}")
    print(f"\nExport this for your agent containers:")
    print(f"  export AGENTCORE_MEMORY_ID={memory_id}")

    return memory_id


def main():
    parser = argparse.ArgumentParser(
        description="Create AgentCore Memory for Retail Dynamic Pricing"
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)",
    )
    args = parser.parse_args()

    try:
        setup_memory(region=args.region)
    except Exception as e:
        print(f"Error creating memory: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
