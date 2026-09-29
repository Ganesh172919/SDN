#!/usr/bin/env python3
"""Run the slow-loop benchmark.

Examples:
  python run_benchmark.py --mock --episodes 10 --mode multi
  python run_benchmark.py --episodes 10 --mode single --base-url http://127.0.0.1:8081/v1
"""

from __future__ import annotations

import argparse
import os

from agentic.benchmark import format_report, run_benchmark
from agentic.model_client import MockModel, OpenAICompatibleClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the SELF-X slow policy governor.")
    parser.add_argument("--mock", action="store_true", help="Use the deterministic mock model.")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--mode", choices=("single", "multi"), default="multi")
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SELFX_LLM_BASE_URL", "http://127.0.0.1:8081/v1"),
    )
    parser.add_argument("--model", default=os.environ.get("SELFX_LLM_MODEL", "local"))
    parser.add_argument("--api-key", default=os.environ.get("SELFX_LLM_API_KEY"))
    args = parser.parse_args()

    if args.mock:
        client = MockModel()
    else:
        client = OpenAICompatibleClient(args.base_url, args.model, args.api_key)

    report = run_benchmark(episodes=args.episodes, mode=args.mode, client=client, seed=args.seed)
    print(format_report(report))
    if not report["scripted_reasoning_pass"] or not report["closed_loop_ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
