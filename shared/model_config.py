"""
Model Configuration for Retail Dynamic Pricing Demo.

Reads model-config.json (written by scripts/select_model.py) and provides
model IDs for all agents. Falls back to defaults if config not found.

Usage:
    from shared.model_config import ORCHESTRATOR_MODEL, SPECIALIST_MODEL
"""
import json
import os
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "model-config.json"

# Defaults (used if model-config.json doesn't exist)
_DEFAULT_ORCHESTRATOR_MODEL = "us.anthropic.claude-opus-4-7"
_DEFAULT_SPECIALIST_MODEL = "us.anthropic.claude-sonnet-4-6"


def _load_config() -> dict:
    """Load model configuration from JSON file."""
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


_config = _load_config()

# Orchestrator model (complex reasoning: orchestration, strategy synthesis)
ORCHESTRATOR_MODEL = os.environ.get(
    "ORCHESTRATOR_MODEL_ID",
    _config.get("modelId", _DEFAULT_ORCHESTRATOR_MODEL),
)

# Specialist model (data analysis: competitive, demand, market, implementation)
SPECIALIST_MODEL = os.environ.get(
    "SPECIALIST_MODEL_ID",
    _config.get("specialistModelId", _DEFAULT_SPECIALIST_MODEL),
)
