"""Run one pricing request through the real agent code, in this process.

The orchestrator's own invoke() runs, unchanged, with one substitution: instead
of calling the deployed specialist runtimes with InvokeAgentRuntime, it calls
their invoke() functions in-process. So the prompts, the parallel fan-out, the
prompt-injection filter and the synthesis prompt are the deployed ones, while the
specialist model is whatever SPECIALIST_MODEL_ID this process was started with.
The agents use the real gateway tools (SigV4) and the stack's guardrail; memory
is off so evaluation runs do not write to the shared memory.

Run as a worker by evals/run_eval.py (one process per model configuration,
because shared/model_config.py reads the model IDs at import):

    python -m evals.pipeline --requests-file r.json --out DIR/outputs/<config>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

_PLACEHOLDER_ARN = "arn:aws:bedrock-agentcore:{region}:000000000000:runtime/eval-{name}"
_ARN_VARS = {
    "COMPETITIVE_INTELLIGENCE_AGENT_ARN": "ci",
    "DEMAND_FORECASTING_AGENT_ARN": "df",
    "MARKET_INTELLIGENCE_AGENT_ARN": "mi",
    "STRATEGY_SYNTHESIS_AGENT_ARN": "ss",
    "IMPLEMENTATION_MONITORING_AGENT_ARN": "im",
}
AGENT_NAMES = {
    "ci": "Competitive Intelligence",
    "df": "Demand Forecasting",
    "mi": "Market Intelligence",
    "ss": "Strategy Synthesis",
}


class Recorder:
    """Per-agent prompts, outputs, timings, token usage, tools and guardrail stops."""

    def __init__(self):
        self.agents: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._current = threading.local()

    def start(self, agent: str, prompt: str) -> None:
        self._current.agent = agent
        with self._lock:
            self.agents[agent] = {"prompt": prompt, "model_calls": []}

    def finish(self, agent: str, output: dict, seconds: float) -> None:
        with self._lock:
            self.agents[agent].update({"output": output, "seconds": round(seconds, 1)})

    def record_model_result(self, result) -> None:
        agent = getattr(self._current, "agent", None)
        if agent is None:
            return
        usage = dict(getattr(result.metrics, "accumulated_usage", {}) or {})
        tools = {name: m.call_count for name, m in (getattr(result.metrics, "tool_metrics", {}) or {}).items()}
        with self._lock:
            self.agents[agent]["model_calls"].append(
                {"stop_reason": str(result.stop_reason), "usage": usage, "tool_calls": tools})

    def mark_dropped(self, agent_label: str) -> None:
        with self._lock:
            for key, name in AGENT_NAMES.items():
                if name == agent_label and key in self.agents:
                    self.agents[key]["dropped_by_injection_filter"] = True


def configure_environment(region: str) -> None:
    """Env the runtime modules read at import: placeholder ARNs, no memory."""
    for var, short in _ARN_VARS.items():
        os.environ.setdefault(var, _PLACEHOLDER_ARN.format(region=region, name=short))
    os.environ.pop("AGENTCORE_MEMORY_ID", None)  # memory off for evaluation runs


def build_pipeline(recorder: Recorder):
    """Import the runtimes and route the orchestrator's specialist calls in-process."""
    from strands.agent import agent as strands_agent

    from backend.agents.agentcore import (
        competitive_intelligence_runtime as ci,
        demand_forecasting_runtime as df,
        market_intelligence_runtime as mi,
        orchestrator_runtime as orchestrator,
        strategy_synthesis_runtime as ss,
    )

    # The orchestrator calls the specialists by ARN. Give each one its own
    # placeholder ARN here, whatever the module read from the environment when
    # it was first imported: equal ARNs would send every call to one agent.
    region = os.environ.get("AWS_REGION", "us-east-1")
    modules = {}
    for constant, short, module in (("CI_ARN", "ci", ci), ("DF_ARN", "df", df), ("MI_ARN", "mi", mi),
                                    ("SS_ARN", "ss", ss)):
        arn = _PLACEHOLDER_ARN.format(region=region, name=short)
        setattr(orchestrator, constant, arn)
        modules[arn] = (short, module)

    def local_invoke(agent_arn, prompt, session_id, timeout_seconds=0):
        short, module = modules[agent_arn]
        recorder.start(short, prompt)
        started = time.monotonic()
        output = module.invoke({"prompt": prompt})
        recorder.finish(short, output, time.monotonic() - started)
        return output

    original_sanitize = orchestrator._sanitize_agent_output

    def recording_sanitize(data, agent_name):
        cleaned = original_sanitize(data, agent_name)
        if data and cleaned == {}:
            recorder.mark_dropped(agent_name)
        return cleaned

    original_call = strands_agent.Agent.__call__

    def recording_call(self, *args, **kwargs):
        result = original_call(self, *args, **kwargs)
        recorder.record_model_result(result)
        return result

    orchestrator._invoke_agent_runtime = local_invoke
    orchestrator._sanitize_agent_output = recording_sanitize
    orchestrator.create_session_manager = lambda **kw: None
    strands_agent.Agent.__call__ = recording_call
    return orchestrator


def run_request(orchestrator, recorder: Recorder, request: dict) -> dict:
    payload = {k: request[k] for k in ("pricing_group", "objectives", "constraints")}
    started = time.monotonic()
    result = orchestrator.invoke(payload)
    return {
        "request": request,
        "orchestrator_result": {k: result.get(k) for k in ("status", "degraded_agents", "error", "metadata")},
        "agents": recorder.agents,
        "seconds": round(time.monotonic() - started, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--requests-file", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    args = parser.parse_args()

    configure_environment(args.region)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    requests = json.loads(Path(args.requests_file).read_text())
    for request in requests:
        recorder = Recorder()
        orchestrator = build_pipeline(recorder)
        print(f"[{os.environ.get('SPECIALIST_MODEL_ID')}] {request['id']} ...", flush=True)
        record = run_request(orchestrator, recorder, request)
        record["specialist_model"] = os.environ.get("SPECIALIST_MODEL_ID")
        (out / f"{request['id']}.json").write_text(json.dumps(record, indent=1, default=str))
        print(f"  {record['orchestrator_result']['status']} in {record['seconds']} s", flush=True)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    main()
