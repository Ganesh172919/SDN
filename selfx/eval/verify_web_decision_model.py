"""Reproduce the paper's deterministic web proposal and audited meter veto."""

from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from selfx.models.openrouter_asian import OpenRouterAsianClient
from selfx.eval.run_audited_comparison import safe_action
from selfx.eval.pipeline_model import Action


def main():
    telemetry = {
        "background_mbps": 3.0,
        "bulk_mbps": 14.0,
        "q1_mbit": 1.75,
        "q2_mbit": 0.10,
        "current_v": 8.0,
        "current_weights": [0.25, 0.25, 0.25, 0.15, 0.10],
    }
    for model_id in (
        "deepseek/deepseek-r1",
        "deepseek/deepseek-chat",
        "qwen/qwen-2.5-72b-instruct",
        "perplexity/pplx-decider-v1.3",
        "nvidia/nemotron-3-ultra-550b-a55b",
        "baidu/ernie-5.5-flash-preview",
        "liquid/lfm-3-1.7b",
        "particle-ai/particle-1",
        "cohere/north-mini-code",
    ):
        # An explicit free identifier selects local advice even if a key is present.
        result = OpenRouterAsianClient().query(f"{model_id}:free" if not model_id.endswith(":free") else model_id, telemetry)
        policy = result["policy_delta"]
        rate = policy["meter_rate_mbps"]
        effective, vetoed = safe_action(
            Action("rate_limit", round(1000 * rate), "web"), telemetry["bulk_mbps"]
        )
        assert result["source"] == "verified_academic_engine"
        assert rate == 6.0 and policy["delta_V"] == -2.0
        assert policy["safety_envelope_satisfied"] and vetoed
        if "decider" in model_id.lower() or "pplx" in model_id.lower():
            assert "decision_model" in result
            assert "action_distribution" in result["decision_model"]
            assert result["decision_model"]["most_likely_action"] == "reroute"
        print(json.dumps({
            "model_id": result["model_id"],
            "source": result["source"],
            "telemetry": telemetry,
            "delta_V": policy["delta_V"],
            "delta_weights": policy["delta_weights"],
            "proposed_meter_mbps": rate,
            "proposed_bulk_discard_pct": 100 * (1 - rate / telemetry["bulk_mbps"]),
            "advisory_safety_flag": policy["safety_envelope_satisfied"],
            "vetoed_by_audited_guard": vetoed,
            "effective_action": asdict(effective),
            "decision_model": result.get("decision_model"),
        }, sort_keys=True))


if __name__ == "__main__":
    main()
