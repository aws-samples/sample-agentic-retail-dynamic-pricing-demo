# Specialist model evaluation

`select_model.py` lets you run the five specialist agents on a cheaper model than the orchestrator (for example Sonnet instead of Opus). This harness checks whether the agents' output holds up on that model before you switch.

## What it runs

Each configuration (a specialist model ID) runs the seven dashboard presets in `requests.json` through the **real agent code** (`pipeline.py`):

- **Orchestrator:** its own `invoke()` runs unchanged, so the prompts, the parallel fan-out, the prompt-injection filter and the synthesis prompt are the deployed ones. Only the specialist calls are made in-process instead of through `InvokeAgentRuntime`, so the model can be swapped without redeploying.
- **Tools and guardrail:** the agents call the deployed AgentCore Gateway tools (SigV4) with the stack's Bedrock guardrail attached.
- **Memory:** off, so evaluation runs don't write to the shared memory.

Each configuration runs in its own process, because the model IDs are read at import time.

## How it scores

`scoring.py` runs two kinds of check.

**Deterministic checks**, which use no model:

| Check | Fails when |
|---|---|
| Agents succeeded | any specialist or the synthesis returned `status: error` |
| Guardrail blocks | the guardrail stopped an agent (these are legitimate requests) |
| Injection-filter drops | the orchestrator's prompt-injection filter dropped a specialist answer |
| Tool use | a specialist answered without calling a gateway tool, so it had no data |
| On topic | a specialist answer doesn't name the requested product group |
| Synthesis JSON | the synthesis didn't return parseable JSON with scenarios |
| Constraints | a scenario's price change exceeds `maxPriceChange`, or its margin is below `minMargin` |

**LLM judge:** a Bedrock model scores the synthesis 1–5 on relevance, grounding in the analyst reports, consistency, actionability and compliance. It sees the request and the agents' outputs, but not which model produced them. It runs at temperature 0 where the model accepts that; newer models such as Claude Opus 5.5 reject the setting, so the judge then uses the model's default sampling and `scores.json` records `"temperature": null`.

The report also lists cycle and synthesis times and token counts per configuration.

## Running it

```bash
source .venv/bin/activate
# Plan and cost note only (nothing runs without --yes):
python -m evals.run_eval
# Both tiers from model-config.json, all 7 requests:
python -m evals.run_eval --yes
# Explicit models, 2 requests, 2 repeats each:
python -m evals.run_eval --config sonnet=us.anthropic.claude-sonnet-5-5 \
    --config opus=us.anthropic.claude-opus-5-5 --requests 2 --repeats 2 --yes
# Score a finished run again (no new cycles; judge calls only), e.g. after a judge error:
python -m evals.run_eval --rescore evals/results/<timestamp>
```

Results go to `evals/results/<timestamp>/` (git-ignored): `report.md`, `scores.json`, `run.json` (the run's settings, used by `--rescore`), and every agent's prompt and output under `outputs/`. A failed judge call is shown in the report and does not stop the scoring.

**Requirements:**
- A deployed stack (the gateway and the guardrail come from it).
- Credentials allowed to call the models, `bedrock-agentcore:InvokeGateway` on the gateway, `bedrock:ApplyGuardrail`, and to read the stack outputs.

**Cost:** each request costs about as much as one dashboard pricing cycle, plus one judge call. The script prints the number of cycles before it starts.

## Reading the results

Switch the specialists only if **all** of these hold:
- the cheaper configuration passes the deterministic checks as often as the other
- it adds no constraint violations or guardrail blocks
- its judge scores are within about 0.3 on each criterion

Caveats:
- **Randomised data:** MCP data is simulated per call, so runs vary even on the same model. Compare means over all requests and use `--repeats` for borderline results.
- **Judge bias:** the judge can favour answers in its own style. Read the rationales in `scores.json` before acting on a small gap.
- **Filter drops are a known false positive:** the injection-filter check flags the orchestrator's `DAN` pattern, which matches words such as "guidance" and "abundant" and the agents' own JSON keys. It is a regression check for that fix, not a model-quality signal.
