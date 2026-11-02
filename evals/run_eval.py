"""Compare specialist models on a fixed set of pricing requests.

    python -m evals.run_eval --yes                       # both tiers from model-config.json
    python -m evals.run_eval --config sonnet=us.anthropic.claude-sonnet-5-5 \\
        --config opus=us.anthropic.claude-opus-5-5 --requests 2 --yes

For each model configuration, runs every request through the real agent code
(evals/pipeline.py: deployed prompts, gateway tools, guardrail), scores each run
(evals/scoring.py) and writes evals/results/<timestamp>/report.md and scores.json.
This calls Bedrock models and is billed; the plan and an estimate are printed
before anything runs, and --yes is required to start.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from evals import scoring  # noqa: E402

REQUESTS_FILE = ROOT / "evals" / "requests.json"
MODEL_CONFIG_FILE = ROOT / "model-config.json"
STACK_NAME = "RetailDynamicPricing"


def default_configs() -> dict[str, str]:
    config = json.loads(MODEL_CONFIG_FILE.read_text()) if MODEL_CONFIG_FILE.exists() else {}
    configs = {}
    if config.get("specialistModelId"):
        configs["specialist-tier"] = config["specialistModelId"]
    if config.get("modelId") and config.get("modelId") != config.get("specialistModelId"):
        configs["orchestrator-tier"] = config["modelId"]
    return configs


def parse_configs(values: list[str]) -> dict[str, str]:
    configs = {}
    for value in values:
        name, sep, model = value.partition("=")
        if not sep or not name or not model:
            raise SystemExit(f"--config must be NAME=MODEL_ID, got {value!r}")
        configs[name] = model
    return configs


def deployed_wiring(region: str, use_guardrail: bool) -> dict[str, str]:
    """Gateway MCP URL and the stack guardrail, as the deployed agents use them."""
    import secure_gateway

    control = boto3.client("bedrock-agentcore-control", region_name=region)
    gateway = secure_gateway.find_gateway(control, secure_gateway.GATEWAY_NAME)
    if gateway is None:
        raise SystemExit(f"Gateway {secure_gateway.GATEWAY_NAME} not found: deploy the stack first (deploy.sh).")
    env = {"AGENTCORE_GATEWAY_ENDPOINT": secure_gateway.mcp_endpoint(gateway), "AGENTCORE_GATEWAY_AUTH": "AWS_IAM"}
    if not use_guardrail:
        env["DISABLE_BEDROCK_GUARDRAILS"] = "true"
        return env
    outputs = {o["OutputKey"]: o["OutputValue"] for o in boto3.client("cloudformation", region_name=region)
               .describe_stacks(StackName=STACK_NAME)["Stacks"][0].get("Outputs", [])}
    if "BedrockGuardrailId" not in outputs:
        raise SystemExit(f"Stack {STACK_NAME} has no BedrockGuardrailId output; deploy the stack or pass --no-guardrail.")
    env.update(BEDROCK_GUARDRAIL_ID=outputs["BedrockGuardrailId"],
               BEDROCK_GUARDRAIL_VERSION=outputs["BedrockGuardrailVersion"])
    return env


def run_worker(config_name: str, model_id: str, requests: list[dict], out_dir: Path, base_env: dict, region: str) -> int:
    worker_out = out_dir / "outputs" / config_name
    worker_out.mkdir(parents=True, exist_ok=True)
    requests_file = worker_out / "requests.json"
    requests_file.write_text(json.dumps(requests))
    env = {**os.environ, **base_env, "SPECIALIST_MODEL_ID": model_id, "AWS_REGION": region}
    log = (worker_out / "worker.log").open("w")
    process = subprocess.run(
        [sys.executable, "-m", "evals.pipeline", "--requests-file", str(requests_file), "--out", str(worker_out),
         "--region", region],
        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=False,
    )
    return process.returncode


RUN_FILE = "run.json"  # the run's parameters, so --rescore can score its outputs again


def load_run(out_dir: Path) -> dict:
    path = out_dir / RUN_FILE
    if not path.exists():
        raise SystemExit(f"{path} not found: --rescore needs a results directory written by evals.run_eval.")
    return json.loads(path.read_text())


def score_outputs(out_dir: Path, run: dict, runtime, judge_model: str | None) -> dict[str, list[dict]]:
    """Deterministic checks and (if judge_model) the judge for every saved output of the run."""
    rows: dict[str, list[dict]] = {}
    for name in run["configs"]:
        rows[name] = []
        for request in run["expanded"]:
            path = out_dir / "outputs" / name / f"{request['id']}.json"
            if not path.exists():
                continue
            record = json.loads(path.read_text())
            row = {"request_id": request["id"], "checks": scoring.deterministic_checks(record), "judge": None}
            if judge_model:
                try:
                    row["judge"] = scoring.judge(record, runtime, judge_model)
                except Exception as e:  # keep scoring the other runs; the report shows the error
                    row["judge_error"] = f"{type(e).__name__}: {e}"[:300]
            rows[name].append(row)
    return rows


def _mean(values: list[float]) -> float | None:
    values = [v for v in values if v is not None]
    return round(statistics.mean(values), 2) if values else None


def summarize(rows: list[dict]) -> dict:
    judged = [r["judge"]["scores"] for r in rows if r.get("judge")]
    return {
        "runs": len(rows),
        "passed": sum(1 for r in rows if r["checks"]["passed"]),
        "agent_failures": sum(1 for r in rows if not r["checks"]["all_agents_succeeded"]),
        "guardrail_blocks": sum(r["checks"]["guardrail_blocks"] for r in rows),
        "injection_filter_drops": sum(len(r["checks"]["injection_filter_drops"]) for r in rows),
        "synthesis_json": sum(1 for r in rows if r["checks"]["synthesis_json"]),
        "constraint_violations": sum(len(r["checks"]["constraint_violations"]) for r in rows),
        "judge": {c: _mean([j[c] for j in judged]) for c in scoring.JUDGE_CRITERIA},
        "judge_overall": _mean([statistics.mean(j.values()) for j in judged]),
        "judge_failures": sum(1 for r in rows if r.get("judge_error")),
        "cycle_seconds": _mean([r["checks"]["cycle_seconds"] for r in rows]),
        "synthesis_seconds": _mean([r["checks"]["seconds"]["ss"] for r in rows]),
        "tokens": {k: sum(r["checks"]["tokens"][k] for r in rows) for k in ("inputTokens", "outputTokens")},
    }


def render_report(meta: dict, summaries: dict[str, dict], rows: dict[str, list[dict]]) -> str:
    lines = [
        f"# Specialist model evaluation, {meta['started']}",
        "",
        f"Requests: {meta['requests']} (evals/requests.json) x repeats {meta['repeats']}. Judge: `{meta['judge_model']}`. "
        f"Guardrail: {meta['guardrail']}. Specialist models:",
        "",
        *[f"- **{name}**: `{model}`" for name, model in meta["configs"].items()],
        "",
        "| | " + " | ".join(summaries) + " |",
        "|---|" + "---|" * len(summaries),
    ]
    def row(label, key, fmt=str):
        lines.append(f"| {label} | " + " | ".join(fmt(s[key]) for s in summaries.values()) + " |")
    row("Runs passing all checks", "passed", str)
    row("Runs with a failed agent", "agent_failures")
    row("Guardrail blocks (should be 0)", "guardrail_blocks")
    row("Answers dropped by the injection filter", "injection_filter_drops")
    row("Synthesis returned JSON", "synthesis_json")
    row("Constraint violations in scenarios", "constraint_violations")
    for criterion in scoring.JUDGE_CRITERIA:
        lines.append(f"| Judge: {criterion} (1-5) | " + " | ".join(str(s["judge"][criterion]) for s in summaries.values()) + " |")
    row("Judge: overall (1-5)", "judge_overall")
    row("Judge calls that failed", "judge_failures")
    row("Mean cycle time (s)", "cycle_seconds")
    row("Mean synthesis time (s)", "synthesis_seconds")
    lines.append("| Input / output tokens | " + " | ".join(
        f"{s['tokens']['inputTokens']:,} / {s['tokens']['outputTokens']:,}" for s in summaries.values()) + " |")
    lines += ["", "## Per request", ""]
    for name, config_rows in rows.items():
        lines += [f"### {name}", "", "| Request | Checks | Judge | Notes |", "|---|---|---|---|"]
        for r in config_rows:
            c = r["checks"]
            notes = [*([f"failed: {', '.join(c['failed_agents'])} ({next(iter(c['failed_agents'].values()))[:80]})"]
                       if c.get("failed_agents") else []),
                     *(c["constraint_violations"][:2]),
                     *([f"dropped by filter: {', '.join(c['injection_filter_drops'])}"] if c["injection_filter_drops"] else []),
                     *([f"no tool calls: {', '.join(c['specialists_without_tool_calls'])}"] if c["specialists_without_tool_calls"] else []),
                     *([f"off topic: {', '.join(c['specialists_off_topic'])}"] if c["specialists_off_topic"] else []),
                     *([f"{c['guardrail_blocks']} guardrail block(s)"] if c["guardrail_blocks"] else []),
                     *([] if c["synthesis_json"] else ["synthesis not JSON"]),
                     *([f"judge failed: {r['judge_error']}"] if r.get("judge_error") else [])]
            score = r["judge"] and round(statistics.mean(r["judge"]["scores"].values()), 1)
            lines.append(f"| {r['request_id']} | {'pass' if c['passed'] else 'FAIL'} | {score or '-'} | "
                         f"{'; '.join(notes)[:300] or '-'} |")
        lines.append("")
    lines += [
        "## Reading this",
        "",
        "- MCP data is simulated and randomised per call, so runs differ even with the same model; compare means "
        "over several requests (and --repeats) rather than single runs.",
        "- The judge is blind to the model but may still favour answers in its own style; check the per-request "
        "rationales in scores.json before acting on a small difference.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", action="append", default=[], metavar="NAME=MODEL_ID",
                        help="specialist model configuration (repeatable; default: both tiers from model-config.json)")
    parser.add_argument("--requests", type=int, default=None, help="use only the first N requests")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--judge-model", default=None, help="default: the orchestrator model in model-config.json")
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--no-guardrail", action="store_true", help="run the agents without the stack guardrail")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    parser.add_argument("--out", default=None)
    parser.add_argument("--rescore", metavar="DIR", default=None,
                        help="score the saved outputs of an earlier run again (no pricing cycles run)")
    parser.add_argument("--yes", action="store_true", help="confirm the Bedrock spend and start")
    args = parser.parse_args()

    judge_model = args.judge_model or (json.loads(MODEL_CONFIG_FILE.read_text()).get("modelId")
                                       if MODEL_CONFIG_FILE.exists() else None)
    if args.no_judge:
        judge_model = None
    if args.rescore:
        out_dir = Path(args.rescore)
        run = load_run(out_dir)
        print(f"Re-scoring {out_dir} ({len(run['configs'])} configuration(s), {len(run['expanded'])} request(s)); "
              f"{len(run['configs']) * len(run['expanded']) if judge_model else 0} judge call(s).")
    else:
        configs = parse_configs(args.config) if args.config else default_configs()
        if not configs:
            raise SystemExit("No model configurations: pass --config NAME=MODEL_ID or run scripts/select_model.py.")
        requests = json.loads(REQUESTS_FILE.read_text())["requests"][: args.requests]
        runs = len(configs) * len(requests) * args.repeats
        print(f"Plan: {len(configs)} configuration(s) x {len(requests)} request(s) x {args.repeats} repeat(s) = "
              f"{runs} pricing cycles ({runs * 4} agent runs), plus {runs if judge_model else 0} judge call(s).")
        for name, model in configs.items():
            print(f"  {name}: {model}")
        print("Each cycle costs roughly what a dashboard cycle costs (four agents, several model calls each).")
        if not args.yes:
            raise SystemExit("Re-run with --yes to start (this is billed).")

        started = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = Path(args.out) if args.out else ROOT / "evals" / "results" / started
        base_env = deployed_wiring(args.region, use_guardrail=not args.no_guardrail)
        run = {
            "started": started, "configs": configs, "requests": len(requests), "repeats": args.repeats,
            "guardrail": "off" if args.no_guardrail else base_env.get("BEDROCK_GUARDRAIL_ID"),
            "expanded": [{**r, "id": f"{r['id']}-r{i + 1}" if args.repeats > 1 else r["id"]}
                         for r in requests for i in range(args.repeats)],
        }
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / RUN_FILE).write_text(json.dumps(run, indent=1))
        for name, model in configs.items():
            t0 = time.monotonic()
            print(f"Running {name} ({model}) ...", flush=True)
            code = run_worker(name, model, run["expanded"], out_dir, base_env, args.region)
            print(f"  worker exit {code} after {int(time.monotonic() - t0)} s (log: outputs/{name}/worker.log)",
                  flush=True)

    rows = score_outputs(out_dir, run, boto3.client("bedrock-runtime", region_name=args.region), judge_model)
    summaries = {name: summarize(r) for name, r in rows.items()}
    meta = {**{k: v for k, v in run.items() if k != "expanded"}, "judge_model": judge_model}
    (out_dir / "scores.json").write_text(json.dumps({"meta": meta, "summaries": summaries, "rows": rows},
                                                    indent=1, default=str))
    (out_dir / "report.md").write_text(render_report(meta, summaries, rows))
    print(f"\nReport: {out_dir / 'report.md'}")
    print(json.dumps(summaries, indent=1))


if __name__ == "__main__":
    main()
