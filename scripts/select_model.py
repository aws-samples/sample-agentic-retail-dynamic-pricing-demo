#!/usr/bin/env python3
"""
Model Selection Script for Retail Dynamic Pricing Demo.

Queries Amazon Bedrock for available Claude models, checks access, and lets
the user pick two models:

- the orchestrator model (recommended: the newest ACTIVE Opus model), used by
  the orchestrator for complex multi-step reasoning
- the specialist model (recommended: the newest ACTIVE Sonnet model), used by
  the five specialist agents for data analysis

Both are written to model-config.json (``modelId`` / ``specialistModelId``),
which deploy_agentcore.py passes to the runtimes as ORCHESTRATOR_MODEL_ID /
SPECIALIST_MODEL_ID. Setting either of those variables in the environment
before running this script skips that prompt and uses the given model ID.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"
DIM = "\033[2m"

# Capability tier ranking (higher = more capable)
CAPABILITY_TIERS = {
    "opus": 4,
    "sonnet": 3,
    "haiku": 2,
}

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "model-config.json"

# (role label, preferred tier, environment override, config key, name key)
ROLES = (
    ("orchestrator", "opus", "ORCHESTRATOR_MODEL_ID", "modelId", "modelName"),
    ("specialist", "sonnet", "SPECIALIST_MODEL_ID", "specialistModelId", "specialistModelName"),
)

# "claude-opus-4-5-20251101-v1:0" / "claude-opus-5-5" (tier, then version) and
# the older "claude-3-5-sonnet-20240620-v1:0" (version, then tier).
_VERSION_AFTER_TIER = re.compile(r"claude-[a-z]+-(\d{1,2})(?:-(\d{1,2}))?(?=-|:|$)")
_VERSION_BEFORE_TIER = re.compile(r"claude-(\d{1,2})(?:-(\d{1,2}))?-[a-z]+")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Select the orchestrator and specialist models for the "
        "Retail Dynamic Pricing Demo deployment."
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Auto-select the recommended orchestrator and specialist models without prompting.",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region for Bedrock API calls (default: us-east-1).",
    )
    parser.add_argument(
        "--output-path",
        default=None,
        help="Path to write model-config.json (default: auto-detect from script location).",
    )
    return parser.parse_args()


def get_capability_tier(model_id: str) -> int:
    """Determine capability tier from model ID."""
    model_id_lower = model_id.lower()
    for tier_name, tier_value in CAPABILITY_TIERS.items():
        if tier_name in model_id_lower:
            return tier_value
    return 1  # Unknown tier gets lowest ranking


def get_tier_name(model_id: str) -> str | None:
    """Return 'opus' / 'sonnet' / 'haiku' for a model ID, or None if unknown."""
    model_id_lower = model_id.lower()
    for tier_name in CAPABILITY_TIERS:
        if tier_name in model_id_lower:
            return tier_name
    return None


def extract_model_version(model_id: str) -> tuple[int, int]:
    """Return the (major, minor) model version, e.g. claude-opus-4-5-... -> (4, 5).

    Newer model IDs carry no release date (claude-opus-5-5), so recency must
    come from the version number, not only the date. Unknown formats -> (0, 0).
    """
    model_id_lower = model_id.lower()
    match = _VERSION_AFTER_TIER.search(model_id_lower) or _VERSION_BEFORE_TIER.search(model_id_lower)
    if not match:
        return (0, 0)
    return (int(match.group(1)), int(match.group(2) or 0))


def extract_version_date(model_id: str) -> str:
    """Extract date string from model ID for recency comparison."""
    parts = model_id.split("-")
    for part in parts:
        if len(part) >= 8 and part[:8].isdigit():
            return part[:8]
    return "00000000"


def get_friendly_name(model_name: str, model_id: str) -> str:
    """Build a friendly display name for the model."""
    if model_name:
        return model_name
    return model_id.split(".")[-1] if "." in model_id else model_id


def to_cross_region_id(model_id: str) -> str:
    """Return the US cross-region inference profile ID for a model ID."""
    return model_id if model_id.startswith("us.") else f"us.{model_id}"


def check_model_access(client, model_id: str) -> bool:
    """Check if the user has access to a specific model."""
    try:
        response = client.get_foundation_model_availability(modelId=model_id)
        auth_status = response.get("authorizationStatus", "")
        entitlement = response.get("entitlementAvailability", "")
        return auth_status == "AUTHORIZED" and entitlement == "AVAILABLE"
    except (ClientError, Exception):
        return False


def format_eol_date(eol_time) -> str:
    """Format the end-of-life timestamp for display."""
    if not eol_time:
        return "Not specified"
    if isinstance(eol_time, datetime):
        return eol_time.strftime("%Y-%m-%d")
    return str(eol_time)


def _lifecycle_status(model: dict) -> str:
    return model.get("modelLifecycle", {}).get("status", "")


def sort_models(models: list) -> list:
    """
    Sort models by recommendation priority.

    Order: ACTIVE first, then LEGACY, then anything else. Within each group,
    capability tier (opus > sonnet > haiku), then version (newer first), then
    release date (newer first).
    """
    status_rank = {"ACTIVE": 0, "LEGACY": 1}

    def key(model: dict):
        model_id = model["modelId"]
        major, minor = extract_model_version(model_id)
        return (
            status_rank.get(_lifecycle_status(model), 2),
            -get_capability_tier(model_id),
            -major,
            -minor,
            -int(extract_version_date(model_id)),
        )

    return sorted(models, key=key)


def find_recommended_index(models: list, tier: str | None = None) -> int:
    """
    Determine which model to recommend from a list sorted by sort_models().

    With ``tier``, prefers the first ACTIVE model of that tier, then the first
    ACTIVE model of any tier. If none are ACTIVE, picks the LEGACY model with
    the latest end-of-life.
    """
    active_indices = [i for i, m in enumerate(models) if _lifecycle_status(m) == "ACTIVE"]
    if tier:
        for i in active_indices:
            if get_tier_name(models[i]["modelId"]) == tier:
                return i
    if active_indices:
        return active_indices[0]

    # No ACTIVE models — pick LEGACY with latest EOL
    best_idx = 0
    best_eol = ""
    for i, m in enumerate(models):
        eol = m.get("modelLifecycle", {}).get("endOfLifeTime")
        eol_str = format_eol_date(eol) if eol else ""
        if eol_str > best_eol:
            best_eol = eol_str
            best_idx = i
    return best_idx


def list_accessible_models(client) -> list:
    """Return the Claude models this account can invoke, sorted by priority."""
    print("Querying available Claude models...")
    try:
        response = client.list_foundation_models(byProvider="anthropic")
    except ClientError as e:
        print(f"{RED}Error listing models: {e}{RESET}")
        sys.exit(1)

    claude_models = [
        m for m in response.get("modelSummaries", []) if "claude" in m.get("modelId", "").lower()
    ]
    if not claude_models:
        print(f"{RED}No Claude models found in this region.{RESET}")
        sys.exit(1)

    print("Checking model access (this may take a moment)...\n")
    accessible = [m for m in claude_models if check_model_access(client, m["modelId"])]
    if not accessible:
        print(f"{RED}No accessible Claude models found.{RESET}")
        print("Ensure you have requested model access in the Bedrock console.")
        sys.exit(1)
    return sort_models(accessible)


def print_model_table(models: list, recommended: dict[int, str]) -> None:
    """Print the model table. ``recommended`` maps a row index to its role label."""
    print(f"{BOLD}{'#':<4}{'Model Name':<35}{'Model ID':<55}{'Status':<25}{'Rec.'}{RESET}")
    print("-" * 125)

    legacy_warnings = []
    for i, model in enumerate(models):
        model_id = model["modelId"]
        model_name = get_friendly_name(model.get("modelName", ""), model_id)
        lifecycle = model.get("modelLifecycle", {})
        status = lifecycle.get("status", "UNKNOWN")

        if status == "ACTIVE":
            status_display = f"{GREEN}ACTIVE{RESET}"
        elif status == "LEGACY":
            eol_str = format_eol_date(lifecycle.get("endOfLifeTime"))
            status_display = f"{YELLOW}\u26a0\ufe0f  LEGACY (EOL: {eol_str}){RESET}"
            legacy_warnings.append((model_name, model_id, eol_str))
        else:
            status_display = f"{DIM}{status}{RESET}"

        roles = recommended.get(i, "")
        rec_indicator = f" {GREEN}\u2605 recommended {roles}{RESET}" if roles else ""
        print(f"{i + 1:<4}{model_name:<35}{to_cross_region_id(model_id):<55}{status_display}{rec_indicator}")

    print()
    for name, mid, eol in legacy_warnings:
        print(
            f"{YELLOW}{BOLD}\u26a0\ufe0f  WARNING:{RESET}{YELLOW} {name} ({mid}) is marked LEGACY by AWS. "
            f"End of life: {eol}. Consider using an ACTIVE model instead.{RESET}"
        )
    if legacy_warnings:
        print()


def prompt_for_index(models: list, role: str, recommended_idx: int) -> int:
    """Ask the user to pick a row for ``role``; Enter accepts the recommendation."""
    default_display = recommended_idx + 1
    while True:
        try:
            choice = input(
                f"Select the {BOLD}{role}{RESET} model [1-{len(models)}] "
                f"(Enter for recommended #{default_display}): "
            ).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSelection cancelled.")
            sys.exit(1)

        if not choice:
            return recommended_idx
        try:
            selected_idx = int(choice) - 1
        except ValueError:
            print("Invalid input. Enter a number or press Enter for the default.")
            continue
        if 0 <= selected_idx < len(models):
            return selected_idx
        print(f"Please enter a number between 1 and {len(models)}.")


def choose_models(models: list, non_interactive: bool, environ=os.environ) -> dict:
    """Pick the orchestrator and specialist models and return the config dict.

    An ORCHESTRATOR_MODEL_ID / SPECIALIST_MODEL_ID environment variable skips
    that role's prompt and is used as given.
    """
    recommended = {role: find_recommended_index(models, tier) for role, tier, *_ in ROLES}
    labels: dict[int, list[str]] = {}
    for role, idx in recommended.items():
        labels.setdefault(idx, []).append(role)
    print_model_table(models, {i: " + ".join(roles) for i, roles in labels.items()})

    config = {}
    for role, _tier, env_var, id_key, name_key in ROLES:
        override = environ.get(env_var, "").strip()
        if override:
            print(f"Using {env_var}={override} for the {role} model (no prompt).")
            config[id_key] = override
            config[name_key] = override
            continue
        if non_interactive:
            idx = recommended[role]
            print(f"Auto-selecting the recommended {role} model (--non-interactive)...")
        else:
            idx = prompt_for_index(models, role, recommended[role])
        model = models[idx]
        config[id_key] = to_cross_region_id(model["modelId"])
        config[name_key] = get_friendly_name(model.get("modelName", ""), model["modelId"])
    return config


def write_config(config: dict, output_path: Path) -> None:
    """Write model-config.json."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def main():
    args = parse_args()
    output_path = Path(args.output_path).resolve() if args.output_path else OUTPUT_PATH

    print(f"\n{BOLD}Bedrock Model Selection{RESET}")
    print("=" * 50)
    print(f"Region: {args.region}")
    print("You will pick two models: one for the orchestrator (complex reasoning)")
    print("and one for the five specialist agents (data analysis).\n")

    try:
        client = boto3.client("bedrock", region_name=args.region)
    except Exception as e:
        print(f"{RED}Error: Could not create Bedrock client: {e}{RESET}")
        sys.exit(1)

    models = list_accessible_models(client)
    config = choose_models(models, args.non_interactive)
    write_config(config, output_path)

    print(f"\n{BOLD}{'=' * 50}{RESET}")
    print(f"{GREEN}{BOLD}\u2713 Models selected successfully{RESET}")
    print(f"  Orchestrator: {config['modelName']}  ({config['modelId']})")
    print(f"  Specialists:  {config['specialistModelName']}  ({config['specialistModelId']})")
    print(f"  Config:       {output_path}")
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    main()
