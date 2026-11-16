"""Timeouts for the pricing-cycle call chain, derived from two settings.

    rdp-api-pricing-cycles (Lambda) --InvokeAgentRuntime--> orchestrator
        orchestrator --> 3 specialists in parallel, then strategy synthesis

Only the two agent read timeouts are settings. Every other value is derived so
that each layer always waits longer than the one below it can take:

    orchestrator worst case  <  Lambda read timeout  <  Lambda timeout  <  stale-cycle threshold

and the Lambda timeout stays within Lambda's 900 s maximum (which also keeps the
orchestrator call under the 15-minute synchronous InvokeAgentRuntime limit).

The values are applied in three places that deploy separately: the orchestrator
container (env vars set by scripts/deploy_agentcore.py), the pricing-cycles
Lambda (env vars and function timeout set by CDK) and deploy.sh. All three
resolve them here, and scripts/verify_deployment.py checks the deployed values
agree.

Settings (seconds), from explicit arguments, then the environment:
    SPECIALIST_TIMEOUT_SECONDS  default 300 (slowest measured specialist: 240 s)
    SYNTHESIS_TIMEOUT_SECONDS   default 180 (measured 71-83 s)

Run `python3 -m shared.cycle_timeouts [--specialist N] [--synthesis N]` to print
the derived chain, or to check values before a deploy (exit 1 if invalid).

Standard library only: deploy.sh runs it before the virtualenv exists.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from dataclasses import dataclass

SPECIALIST_ENV = "SPECIALIST_TIMEOUT_SECONDS"
SYNTHESIS_ENV = "SYNTHESIS_TIMEOUT_SECONDS"
DEFAULT_SPECIALIST_SECONDS = 300
DEFAULT_SYNTHESIS_SECONDS = 180

# Fixed retry policy (orchestrator_runtime.py). The orchestrator retries only
# failures that are retryable and faster than FAST_FAILURE_SECONDS.
CONNECT_TIMEOUT_SECONDS = 10
MAX_RETRIES = 2
FAST_FAILURE_SECONDS = 15
RETRY_BACKOFF_SECONDS = 1.0

# Margins between layers.
LAMBDA_READ_MARGIN_SECONDS = 60  # orchestrator worst case -> Lambda read timeout (rounded up to a minute)
LAMBDA_TIMEOUT_MARGIN_SECONDS = 60  # Lambda read timeout -> function timeout (time to record FAILED)
STALE_MARGIN_SECONDS = 180  # function timeout -> a cycle is declared dead

LAMBDA_MAX_TIMEOUT_SECONDS = 900
MIN_AGENT_TIMEOUT_SECONDS = 30  # also must exceed FAST_FAILURE_SECONDS


class InvalidTimeouts(ValueError):
    """The timeout settings cannot form a valid chain."""


# Retry time one call can add on top of its read timeout: MAX_RETRIES fast
# failures plus the backoff before each retry.
RETRY_OVERHEAD_SECONDS = MAX_RETRIES * FAST_FAILURE_SECONDS + sum(
    RETRY_BACKOFF_SECONDS * 2**attempt for attempt in range(MAX_RETRIES)
)


def _ceil_minute(seconds: float) -> int:
    return int(math.ceil(seconds / 60.0) * 60)


@dataclass(frozen=True)
class CycleTimeouts:
    specialist: int = DEFAULT_SPECIALIST_SECONDS
    synthesis: int = DEFAULT_SYNTHESIS_SECONDS

    def __post_init__(self) -> None:
        for name, value in (("specialist", self.specialist), ("synthesis", self.synthesis)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise InvalidTimeouts(f"{name} timeout must be a whole number of seconds, got {value!r}")
            if value < MIN_AGENT_TIMEOUT_SECONDS:
                raise InvalidTimeouts(f"{name} timeout must be at least {MIN_AGENT_TIMEOUT_SECONDS} s, got {value} s")
        if self.lambda_timeout > LAMBDA_MAX_TIMEOUT_SECONDS:
            raise InvalidTimeouts(
                f"specialist ({self.specialist} s) + synthesis ({self.synthesis} s) = "
                f"{self.specialist + self.synthesis} s is too long: the pricing-cycles Lambda would need a "
                f"{self.lambda_timeout} s timeout, over Lambda's {LAMBDA_MAX_TIMEOUT_SECONDS} s maximum. "
                f"Keep the sum at or below {max_agent_seconds_total()} s."
            )

    @property
    def orchestrator_worst_case(self) -> int:
        """Longest an orchestrator invocation can take: both phases at their timeout plus retries."""
        return int(math.ceil(self.specialist + self.synthesis + 2 * RETRY_OVERHEAD_SECONDS))

    @property
    def lambda_read_timeout(self) -> int:
        """Read timeout of the Lambda's call to the orchestrator."""
        return _ceil_minute(self.orchestrator_worst_case + LAMBDA_READ_MARGIN_SECONDS)

    @property
    def lambda_timeout(self) -> int:
        """Function timeout of rdp-api-pricing-cycles."""
        return self.lambda_read_timeout + LAMBDA_TIMEOUT_MARGIN_SECONDS

    @property
    def stale_cycle_seconds(self) -> int:
        """Age after which a still-running cycle is reported as FAILED."""
        return self.lambda_timeout + STALE_MARGIN_SECONDS

    def agent_environment(self) -> dict[str, str]:
        """Env vars for the orchestrator runtime."""
        return {SPECIALIST_ENV: str(self.specialist), SYNTHESIS_ENV: str(self.synthesis)}

    def lambda_environment(self) -> dict[str, str]:
        """Env vars for rdp-api-pricing-cycles."""
        return {
            "ORCHESTRATOR_READ_TIMEOUT_SECONDS": str(self.lambda_read_timeout),
            "STALE_CYCLE_SECONDS": str(self.stale_cycle_seconds),
        }

    def describe(self) -> str:
        return (
            f"specialist {self.specialist} s, synthesis {self.synthesis} s -> orchestrator worst case "
            f"{self.orchestrator_worst_case} s < Lambda read timeout {self.lambda_read_timeout} s < "
            f"Lambda timeout {self.lambda_timeout} s < stale after {self.stale_cycle_seconds} s"
        )


def max_agent_seconds_total() -> int:
    """Largest specialist + synthesis sum that fits under Lambda's maximum timeout."""
    budget = LAMBDA_MAX_TIMEOUT_SECONDS - LAMBDA_TIMEOUT_MARGIN_SECONDS - LAMBDA_READ_MARGIN_SECONDS
    return int(math.floor(budget - 2 * RETRY_OVERHEAD_SECONDS))


def _parse(name: str, value: object, default: int) -> int:
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    text = str(value).strip()
    if not text.isdigit():
        raise InvalidTimeouts(f"{name} must be a whole number of seconds, got {value!r}")
    return int(text)


def resolve(specialist: object = None, synthesis: object = None, environ: dict | None = None) -> CycleTimeouts:
    """Timeouts from explicit values (CLI / CDK context), else the environment, else defaults."""
    env = os.environ if environ is None else environ
    return CycleTimeouts(
        specialist=_parse(SPECIALIST_ENV, specialist if specialist not in (None, "") else env.get(SPECIALIST_ENV),
                          DEFAULT_SPECIALIST_SECONDS),
        synthesis=_parse(SYNTHESIS_ENV, synthesis if synthesis not in (None, "") else env.get(SYNTHESIS_ENV),
                         DEFAULT_SYNTHESIS_SECONDS),
    )


DEFAULT = CycleTimeouts()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check pricing-cycle timeout settings and print the derived chain.")
    parser.add_argument("--specialist", default=None, help=f"specialist read timeout, s (env {SPECIALIST_ENV})")
    parser.add_argument("--synthesis", default=None, help=f"strategy synthesis read timeout, s (env {SYNTHESIS_ENV})")
    args = parser.parse_args(argv)
    try:
        timeouts = resolve(args.specialist, args.synthesis)
    except InvalidTimeouts as e:
        print(f"Error: invalid pricing-cycle timeouts: {e}", file=sys.stderr)
        return 1
    print(timeouts.describe())
    return 0


if __name__ == "__main__":
    sys.exit(main())
