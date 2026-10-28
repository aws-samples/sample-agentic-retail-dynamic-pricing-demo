"""Tests for scripts/select_model.py (tiered orchestrator / specialist selection).

No AWS calls: the Bedrock client is a small fake and input() is patched.
"""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import select_model  # noqa: E402


def _model(model_id: str, name: str, status: str = "ACTIVE") -> dict:
    return {"modelId": model_id, "modelName": name, "modelLifecycle": {"status": status}}


# Mirrors the list a new us-east-1 account showed during the fresh deploy:
# dated and undated IDs mixed, plus LEGACY entries.
CATALOG = [
    _model("anthropic.claude-opus-4-5-20251101-v1:0", "Claude Opus 4.5"),
    _model("anthropic.claude-opus-5-5", "Claude Opus 5.5"),
    _model("anthropic.claude-opus-4-8", "Claude Opus 4.8"),
    _model("anthropic.claude-sonnet-4-6", "Claude Sonnet 4.6"),
    _model("anthropic.claude-sonnet-5-5", "Claude Sonnet 5.5"),
    _model("anthropic.claude-sonnet-5", "Claude Sonnet 5"),
    _model("anthropic.claude-haiku-5-5", "Claude Haiku 5.5"),
    _model("anthropic.claude-opus-4-1-20250805-v1:0", "Claude Opus 4.1", "LEGACY"),
    _model("anthropic.claude-sonnet-4-5-20250929-v1:0", "Claude Sonnet 4.5", "LEGACY"),
]


class FakeBedrock:
    def __init__(self, models, inaccessible=()):
        self._models = models
        self._inaccessible = set(inaccessible)

    def list_foundation_models(self, byProvider):
        assert byProvider == "anthropic"
        return {"modelSummaries": list(self._models)}

    def get_foundation_model_availability(self, modelId):
        if modelId in self._inaccessible:
            return {"authorizationStatus": "NOT_AUTHORIZED", "entitlementAvailability": "AVAILABLE"}
        return {"authorizationStatus": "AUTHORIZED", "entitlementAvailability": "AVAILABLE"}


@pytest.fixture
def models():
    return select_model.sort_models(CATALOG)


class TestVersionParsing:
    @pytest.mark.parametrize(
        "model_id, expected",
        [
            ("anthropic.claude-opus-4-5-20251101-v1:0", (4, 5)),
            ("anthropic.claude-opus-5-5", (5, 5)),
            ("us.anthropic.claude-opus-5", (5, 0)),
            ("anthropic.claude-opus-4-6-v1", (4, 6)),
            ("anthropic.claude-opus-4-20250514-v1:0", (4, 0)),
            ("anthropic.claude-3-5-sonnet-20240620-v1:0", (3, 5)),
            ("anthropic.some-other-model", (0, 0)),
        ],
    )
    def test_extract_model_version(self, model_id, expected):
        assert select_model.extract_model_version(model_id) == expected


class TestSorting:
    def test_newest_version_wins_over_a_dated_older_model(self, models):
        # Regression: undated IDs used to sort below dated ones, so the
        # recommendation was Opus 4.5 although Opus 5.5 was available.
        ids = [m["modelId"] for m in models]
        assert ids.index("anthropic.claude-opus-5-5") < ids.index("anthropic.claude-opus-4-8")
        assert ids.index("anthropic.claude-opus-4-8") < ids.index("anthropic.claude-opus-4-5-20251101-v1:0")

    def test_active_before_legacy(self, models):
        statuses = [m["modelLifecycle"]["status"] for m in models]
        assert statuses == sorted(statuses, key=lambda s: s != "ACTIVE")

    def test_tier_order_within_active(self, models):
        active = [m["modelId"] for m in models if m["modelLifecycle"]["status"] == "ACTIVE"]
        tiers = [select_model.get_tier_name(m) for m in active]
        assert tiers == ["opus"] * 3 + ["sonnet"] * 3 + ["haiku"]


class TestRecommendation:
    def test_orchestrator_recommends_newest_opus(self, models):
        idx = select_model.find_recommended_index(models, "opus")
        assert models[idx]["modelId"] == "anthropic.claude-opus-5-5"

    def test_specialist_recommends_newest_sonnet(self, models):
        idx = select_model.find_recommended_index(models, "sonnet")
        assert models[idx]["modelId"] == "anthropic.claude-sonnet-5-5"

    def test_falls_back_to_first_active_when_tier_missing(self):
        only_opus = select_model.sort_models([_model("anthropic.claude-opus-5-5", "Claude Opus 5.5")])
        assert select_model.find_recommended_index(only_opus, "sonnet") == 0

    def test_legacy_only_picks_latest_eol(self):
        legacy = [
            {"modelId": "anthropic.claude-opus-4-1", "modelLifecycle": {"status": "LEGACY", "endOfLifeTime": "2027-01-08"}},
            {"modelId": "anthropic.claude-sonnet-4-5", "modelLifecycle": {"status": "LEGACY", "endOfLifeTime": "2027-04-08"}},
        ]
        assert select_model.find_recommended_index(legacy, "opus") == 1


class TestChooseModels:
    def test_non_interactive_picks_tiered_pair(self, models):
        config = select_model.choose_models(models, non_interactive=True, environ={})
        assert config == {
            "modelId": "us.anthropic.claude-opus-5-5",
            "modelName": "Claude Opus 5.5",
            "specialistModelId": "us.anthropic.claude-sonnet-5-5",
            "specialistModelName": "Claude Sonnet 5.5",
        }

    def test_enter_twice_accepts_both_recommendations(self, models, monkeypatch):
        answers = iter(["", ""])
        monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
        config = select_model.choose_models(models, non_interactive=False, environ={})
        assert config["modelId"] == "us.anthropic.claude-opus-5-5"
        assert config["specialistModelId"] == "us.anthropic.claude-sonnet-5-5"

    def test_user_can_pick_each_role_independently(self, models, monkeypatch):
        ids = [m["modelId"] for m in models]
        opus_48 = ids.index("anthropic.claude-opus-4-8") + 1
        haiku = ids.index("anthropic.claude-haiku-5-5") + 1
        answers = iter(["abc", "99", str(opus_48), str(haiku)])  # invalid, out of range, then valid
        monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
        config = select_model.choose_models(models, non_interactive=False, environ={})
        assert config["modelId"] == "us.anthropic.claude-opus-4-8"
        assert config["specialistModelId"] == "us.anthropic.claude-haiku-5-5"

    def test_env_override_skips_only_that_prompt(self, models, monkeypatch):
        prompts = []

        def fake_input(prompt):
            prompts.append(prompt)
            return ""

        monkeypatch.setattr("builtins.input", fake_input)
        config = select_model.choose_models(
            models, non_interactive=False, environ={"SPECIALIST_MODEL_ID": "us.anthropic.claude-sonnet-4-6"}
        )
        assert config["specialistModelId"] == "us.anthropic.claude-sonnet-4-6"
        assert config["modelId"] == "us.anthropic.claude-opus-5-5"
        assert len(prompts) == 1 and "orchestrator" in prompts[0]

    def test_cancel_exits_non_zero(self, models, monkeypatch):
        def cancel(_prompt):
            raise KeyboardInterrupt

        monkeypatch.setattr("builtins.input", cancel)
        with pytest.raises(SystemExit) as exc:
            select_model.choose_models(models, non_interactive=False, environ={})
        assert exc.value.code == 1


class TestMain:
    def test_main_writes_both_tiers(self, tmp_path, monkeypatch):
        out = tmp_path / "model-config.json"
        fake = FakeBedrock(CATALOG, inaccessible={"anthropic.claude-opus-5-5"})
        monkeypatch.setattr(select_model.boto3, "client", lambda *_a, **_k: fake)
        monkeypatch.setattr(sys, "argv", ["select_model.py", "--non-interactive", "--output-path", str(out)])
        monkeypatch.delenv("ORCHESTRATOR_MODEL_ID", raising=False)
        monkeypatch.delenv("SPECIALIST_MODEL_ID", raising=False)

        select_model.main()

        config = json.loads(out.read_text())
        # Opus 5.5 is not accessible, so the next-newest Opus is recommended.
        assert config["modelId"] == "us.anthropic.claude-opus-4-8"
        assert config["specialistModelId"] == "us.anthropic.claude-sonnet-5-5"

    def test_config_feeds_deploy_agentcore(self, tmp_path, monkeypatch, models):
        import deploy_agentcore

        out = tmp_path / "model-config.json"
        select_model.write_config(select_model.choose_models(models, True, environ={}), out)
        monkeypatch.setattr(deploy_agentcore, "MODEL_CONFIG_FILE", out)

        assert deploy_agentcore.load_model_environment() == {
            "ORCHESTRATOR_MODEL_ID": "us.anthropic.claude-opus-5-5",
            "SPECIALIST_MODEL_ID": "us.anthropic.claude-sonnet-5-5",
        }
