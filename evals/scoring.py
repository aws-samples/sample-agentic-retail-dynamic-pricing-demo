"""Scoring for evaluation runs: deterministic checks plus an LLM judge.

Deterministic checks (no model call), per request:
- every specialist and the synthesis returned status "success"
- no agent was stopped by the guardrail (these are legitimate requests)
- the orchestrator's prompt-injection filter dropped no specialist answer
- every specialist called at least one gateway tool (an answer without tool
  data is made up)
- every specialist answer names the requested product group
- the synthesis returned parseable JSON with scenarios, and no scenario breaks
  the request's maxPriceChange / minMargin constraints

The judge (a Bedrock model, blind to which model produced the answers; temperature
0 where the model accepts it) scores the synthesis 1-5 on relevance, grounding,
consistency, actionability and compliance.
"""

from __future__ import annotations

import json
import re
from typing import Any

JUDGE_CRITERIA = ("relevance", "grounding", "consistency", "actionability", "compliance")
SPECIALISTS = ("ci", "df", "mi")

JUDGE_PROMPT = """You are reviewing the output of an AI pricing system for a retailer. Score the final
recommendation (STRATEGY SYNTHESIS) against the request and the three analyst reports it was based on.

REQUEST
Product group: {pricing_group}
Objectives: {objectives}
Constraints: {constraints} (minMargin and maxPriceChange are percentages)

ANALYST REPORTS
[Competitive intelligence]
{ci}

[Demand forecasting]
{df}

[Market intelligence]
{mi}

STRATEGY SYNTHESIS
{ss}

Score each criterion from 1 (poor) to 5 (excellent):
- relevance: addresses the requested product group, objectives and constraints
- grounding: its numbers and claims come from the analyst reports, not invented
- consistency: no contradictions (for example a price cut presented as margin protection without reason)
- actionability: specific price recommendations with rationale and risks
- compliance: stays within maxPriceChange and minMargin, respects cost/MAP floors, and suggests nothing
  anti-competitive or discriminatory

Reply with only a JSON object: {{"scores": {{"relevance": n, "grounding": n, "consistency": n,
"actionability": n, "compliance": n}}, "rationale": "<two sentences>"}}"""

_FENCED_JSON = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)


def result_text(agent: dict | None) -> str:
    output = (agent or {}).get("output") or {}
    return str(output.get("result", "")) if isinstance(output, dict) else str(output)


def extract_json(text: str) -> Any | None:
    """First JSON object in the text: a fenced ```json block, else the outermost {...}."""
    candidates = _FENCED_JSON.findall(text)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except ValueError:
            continue
    return None


def _scenarios(data: Any) -> list[dict]:
    """The list of scenario objects in the synthesis JSON, wherever the model put it."""
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if not isinstance(data, dict):
        return []
    for key, value in data.items():
        if "scenario" in key.lower() and isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    for value in data.values():
        found = _scenarios(value)
        if found:
            return found
    return []


def _numbers(obj: Any, include: tuple[str, ...], exclude: tuple[str, ...] = ()) -> list[float]:
    """Numeric values under keys containing any `include` word (and no `exclude` word), any depth."""
    found = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            k = key.lower().replace("_", "")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if any(w in k for w in include) and not any(w in k for w in exclude):
                    found.append(float(value))
            else:
                found.extend(_numbers(value, include, exclude))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_numbers(item, include, exclude))
    return found


def _as_percent(value: float) -> float:
    return value * 100 if abs(value) <= 1 else value


def constraint_violations(scenarios: list[dict], constraints: dict) -> list[str]:
    """Scenario price changes above maxPriceChange or margins below minMargin (both in percent)."""
    max_change = constraints.get("maxPriceChange")
    min_margin = constraints.get("minMargin")
    problems = []
    for index, scenario in enumerate(scenarios, start=1):
        name = scenario.get("name") or scenario.get("strategy") or scenario.get("scenario_name") or f"#{index}"
        if max_change is not None:
            for change in _numbers(scenario, ("changepercent", "changepct", "pricechange", "percentchange"),
                                   ("units", "volume", "demand", "revenue", "margin")):
                if abs(_as_percent(change)) > max_change + 0.05:
                    problems.append(f"{name}: price change {change:g} exceeds maxPriceChange {max_change}")
        if min_margin is not None:
            for margin in _numbers(scenario, ("margin",), ("change", "delta", "target", "min", "max", "impact",
                                                           "usd", "dollar", "amount")):
                if 0 <= abs(margin) <= 100 and _as_percent(margin) < min_margin - 0.05:
                    problems.append(f"{name}: margin {margin:g} below minMargin {min_margin}")
    return problems


def mentions_group(text: str, pricing_group: str) -> bool:
    words = [w for w in re.split(r"[-&\s]+", pricing_group.lower()) if len(w) > 2]
    lowered = text.lower()
    return any(w in lowered for w in words)


def deterministic_checks(record: dict) -> dict:
    """Pass/fail checks and measurements for one request's run."""
    agents = record.get("agents", {})
    request = record["request"]
    checks: dict[str, Any] = {}
    statuses = {k: ((agents.get(k) or {}).get("output") or {}).get("status") for k in (*SPECIALISTS, "ss")}
    checks["all_agents_succeeded"] = all(s == "success" for s in statuses.values())
    checks["failed_agents"] = {
        k: str(((agents.get(k) or {}).get("output") or {}).get("error") or result_text(agents.get(k))
               or f"status {s}")[:120]
        for k, s in statuses.items() if s != "success"
    }
    stops = [c["stop_reason"] for a in agents.values() for c in a.get("model_calls", [])]
    checks["guardrail_blocks"] = sum(1 for s in stops if "guardrail" in s)
    checks["injection_filter_drops"] = [k for k, a in agents.items() if a.get("dropped_by_injection_filter")]
    tool_calls = {k: sum(n for c in (agents.get(k) or {}).get("model_calls", []) for n in c["tool_calls"].values())
                  for k in SPECIALISTS}
    checks["specialists_without_tool_calls"] = [k for k, n in tool_calls.items() if n == 0]
    checks["specialists_off_topic"] = [k for k in SPECIALISTS
                                       if not mentions_group(result_text(agents.get(k)), request["pricing_group"])]
    synthesis = extract_json(result_text(agents.get("ss")))
    scenarios = _scenarios(synthesis)
    checks["synthesis_json"] = synthesis is not None
    checks["synthesis_scenarios"] = len(scenarios)
    checks["constraint_violations"] = constraint_violations(scenarios, request.get("constraints", {}))
    checks["passed"] = (
        checks["all_agents_succeeded"] and checks["guardrail_blocks"] == 0
        and not checks["injection_filter_drops"] and not checks["specialists_without_tool_calls"]
        and not checks["specialists_off_topic"] and checks["synthesis_scenarios"] > 0
        and not checks["constraint_violations"]
    )
    usage = {"inputTokens": 0, "outputTokens": 0}
    for agent in agents.values():
        for call in agent.get("model_calls", []):
            for key in usage:
                usage[key] += int(call["usage"].get(key, 0))
    checks["tokens"] = usage
    checks["seconds"] = {k: (agents.get(k) or {}).get("seconds") for k in (*SPECIALISTS, "ss")}
    checks["cycle_seconds"] = record.get("seconds")
    return checks


def judge_prompt(record: dict, max_chars: int = 6000) -> str:
    request = record["request"]
    agents = record.get("agents", {})
    return JUDGE_PROMPT.format(
        pricing_group=request["pricing_group"],
        objectives=", ".join(request["objectives"]),
        constraints=json.dumps(request.get("constraints", {})),
        **{k: result_text(agents.get(k))[:max_chars] or "(no output)" for k in (*SPECIALISTS, "ss")},
    )


def parse_judgement(text: str) -> dict | None:
    data = extract_json(text)
    if not isinstance(data, dict) or not isinstance(data.get("scores"), dict):
        return None
    scores = {}
    for criterion in JUDGE_CRITERIA:
        value = data["scores"].get(criterion)
        if not isinstance(value, (int, float)) or not 1 <= value <= 5:
            return None
        scores[criterion] = float(value)
    return {"scores": scores, "rationale": str(data.get("rationale", ""))[:500]}


def _rejects_temperature(error: Exception) -> bool:
    """Newer Claude models reject the temperature setting (ValidationException)."""
    response = getattr(error, "response", None) or {}
    return (response.get("Error", {}).get("Code") == "ValidationException"
            and "temperature" in str(response.get("Error", {}).get("Message", "")))


# Room for a reasoning model's thinking plus the JSON answer: Claude Opus 5.5
# reasons first and used 917-1,260 output tokens per judgement (it spent all of
# an earlier 600-token limit on reasoning and wrote no answer).
JUDGE_MAX_TOKENS = 4000


class JudgeFailed(RuntimeError):
    """The judge model gave no usable score."""


def judge(record: dict, runtime_client, model_id: str) -> dict:
    """Ask the judge model; one retry if the reply is not valid JSON. Raises JudgeFailed after that.

    Uses temperature 0 where the model accepts it, and the model's default
    sampling where it does not (the reply then records temperature None).
    """
    prompt = judge_prompt(record)
    inference = {"temperature": 0, "maxTokens": JUDGE_MAX_TOKENS}
    stop_reason = None
    for _ in range(2):
        request = {"modelId": model_id, "messages": [{"role": "user", "content": [{"text": prompt}]}],
                   "inferenceConfig": inference}
        try:
            response = runtime_client.converse(**request)
        except Exception as e:  # botocore ClientError; checked below so other errors propagate
            if "temperature" not in inference or not _rejects_temperature(e):
                raise
            inference = {k: v for k, v in inference.items() if k != "temperature"}
            response = runtime_client.converse(**{**request, "inferenceConfig": inference})
        text = "".join(block.get("text", "") for block in response["output"]["message"]["content"])
        stop_reason = response.get("stopReason")
        parsed = parse_judgement(text)
        if parsed:
            parsed["usage"] = response.get("usage", {})
            parsed["temperature"] = inference.get("temperature")
            return parsed
    raise JudgeFailed(f"no valid JSON score in 2 replies (last stop reason: {stop_reason})")
