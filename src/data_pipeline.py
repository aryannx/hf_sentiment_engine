from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Tuple

from src.core.logging_utils import get_logger

LOG = get_logger("data_pipeline")


def _run_step(name: str, command: List[str]) -> Tuple[str, bool, float]:
    """Run a single pipeline step via subprocess and return status."""
    start = datetime.utcnow()
    LOG.info({"event": "step_start", "step": name, "cmd": " ".join(command)})
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        ok = result.returncode == 0
        if not ok:
            LOG.error(
                {
                    "event": "step_failed",
                    "step": name,
                    "returncode": result.returncode,
                    "stderr": result.stderr,
                }
            )
        else:
            LOG.info({"event": "step_complete", "step": name})
        elapsed = (datetime.utcnow() - start).total_seconds()
        return name, ok, elapsed
    except Exception as exc:  # pragma: no cover - defensive
        elapsed = (datetime.utcnow() - start).total_seconds()
        LOG.error({"event": "step_error", "step": name, "error": str(exc)})
        return name, False, elapsed


def build_default_steps(cache_root: Path, force_refresh: bool) -> List[Tuple[str, List[str]]]:
    """Default nightly schedule expressed as (name, command)."""
    steps = [
        (
            "warm_cache",
            [
                sys.executable,
                "-m",
                "src.main",
                "--healthcheck",
            ],
        ),
        (
            "equities_watchlist",
            [
                sys.executable,
                "-m",
                "src.main",
                "--watchlist",
                "configs/universes/core_equities.yaml",
                "--mode",
                "position",
                "--credit_overlay",
            ]
            + (["--force_refresh"] if force_refresh else []),
        ),
        (
            "credit_oas",
            [
                sys.executable,
                "-m",
                "src.credit.credit_backtester",
                "--period",
                "3y",
                "--use_percentile",
                "--lower_pct",
                "10",
                "--upper_pct",
                "90",
            ]
            + (["--force_refresh"] if force_refresh else []),
        ),
        (
            "volatility",
            [
                sys.executable,
                "-m",
                "src.volatility.volatility_backtester",
                "--period",
                "2y",
                "--term_structure",
                "contango",
            ],
        ),
        (
            "dq_checks",
            [
                sys.executable,
                "-m",
                "src.data.dq_runner",
            ],
        ),
    ]
    LOG.info(
        {
            "event": "schedule_built",
            "steps": [name for name, _ in steps],
            "cache_root": str(cache_root),
            "force_refresh": force_refresh,
        }
    )
    return steps


def run_schedule(steps: Iterable[Tuple[str, List[str]]]) -> None:
    results = []
    for name, cmd in steps:
        results.append(_run_step(name, cmd))
    summary = {
        "event": "pipeline_summary",
        "results": [{"step": s, "ok": ok, "secs": secs} for s, ok, secs in results],
    }
    LOG.info(summary)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Data pipeline orchestrator")
    parser.add_argument(
        "--cache_root",
        default="data/cache",
        help="Root directory for cached data (for logging only).",
    )
    parser.add_argument(
        "--force_refresh",
        action="store_true",
        help="Propagate force refresh flags to fetchers where applicable.",
    )
    parser.add_argument(
        "--steps",
        nargs="*",
        default=None,
        help="Override default steps with custom commands: name=cmd1,cmd2,...",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cache_root = Path(args.cache_root)
    if args.steps:
        custom_steps: List[Tuple[str, List[str]]] = []
        for raw in args.steps:
            if "=" not in raw:
                raise ValueError("Custom step format must be name=cmd1,cmd2,...")
            name, raw_cmd = raw.split("=", 1)
            cmd = raw_cmd.split(",")
            custom_steps.append((name, cmd))
        steps = custom_steps
    else:
        steps = build_default_steps(cache_root, args.force_refresh)
    run_schedule(steps)


if __name__ == "__main__":
    main()

