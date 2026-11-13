"""
Tests for the pipeline study: the datapath invariants, the optimiser, the
free-tier client's record/replay contract, and the reported-results contract.

These are the properties the paper's claims rest on, so they are tested rather
than assumed. None of them needs a network or a credential.
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SELFX_ROOT = PROJECT_ROOT / "selfx"
for path in (str(PROJECT_ROOT), str(SELFX_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from agent.llm_decider import (  # noqa: E402
    DeciderError,
    FreeModelDecider,
    extract_json_object,
    prompt_key,
    validate_action,
    validate_critique,
    validate_policy,
)
from eval.pipeline_model import (  # noqa: E402
    BUFFER_MBIT,
    C_ALTERNATE_MBPS,
    C_PRIMARY_MBPS,
    TAU_SEC,
    Action,
    PipelineDPP,
    TabularQController,
    Telemetry,
    TwoPathDatapath,
    backlog_bound_mbit,
    demand_series,
    oracle_floor,
    threshold_controller,
    window_reward,
)
from traffic_gen import generate_schedule  # noqa: E402


# --------------------------------------------------------------------------- #
# Datapath invariants
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("seed", [1, 7, 42, 1900])
def test_bit_conservation_holds_under_random_load(seed: int) -> None:
    """Q + lambda*tau == served + overflow + Q' on every slot, for any input."""
    rng = random.Random(seed)
    datapath = TwoPathDatapath()
    for _ in range(2000):
        mice = rng.uniform(0.0, 8.0)
        elephant = rng.uniform(0.0, 25.0)
        kind = rng.choice(["no_op", "reroute", "rate_limit"])
        rate = rng.randint(512, 12000) if kind == "rate_limit" else None
        # step() raises on a conservation violation, so reaching the end is the assertion
        datapath.step(mice, elephant, Action(kind, rate))
    assert datapath.conservation_error_mbit < 1e-9


def test_queue_never_exceeds_the_buffer() -> None:
    datapath = TwoPathDatapath()
    for _ in range(500):
        datapath.step(5.0, 30.0, Action("no_op"))
        assert all(0.0 <= q <= BUFFER_MBIT + 1e-12 for q in datapath.queue)


def test_rate_limit_actually_meters_traffic() -> None:
    """A meter must reduce admitted traffic, not just relabel it."""
    unmetered = TwoPathDatapath().step(3.0, 12.0, Action("no_op"))
    metered = TwoPathDatapath().step(3.0, 12.0, Action("rate_limit", 2000))
    assert metered.meter_mbit > 0
    assert metered.meter_mbit == pytest.approx((12.0 - 2.0) * TAU_SEC)
    assert metered.served_mbit < unmetered.served_mbit + 1e-12


def test_reroute_moves_load_to_the_alternate_path() -> None:
    datapath = TwoPathDatapath()
    for _ in range(50):
        datapath.step(3.0, 9.0, Action("reroute"))
    # the elephant alone is below the alternate capacity, so it should drain
    assert datapath.queue[1] < BUFFER_MBIT
    assert datapath.queue[0] == pytest.approx(0.0, abs=1e-9)


def test_average_queue_integral_matches_numeric_integration() -> None:
    """The closed-form slot-average must agree with brute-force integration."""
    for initial, net in [(0.0, 5.0), (1.0, -3.0), (0.3, 12.0), (1.9, 0.4), (0.5, 0.0)]:
        closed = TwoPathDatapath._average_queue(initial, net, TAU_SEC)
        steps = 20000
        dt = TAU_SEC / steps
        total = 0.0
        q = initial
        for _ in range(steps):
            total += q * dt
            q = min(BUFFER_MBIT, max(0.0, q + net * dt))
        assert closed == pytest.approx(total / TAU_SEC, abs=2e-3)


def test_delay_rises_with_backlog() -> None:
    empty = TwoPathDatapath().step(3.0, 2.0, Action("no_op"))
    loaded = TwoPathDatapath()
    for _ in range(30):
        loaded.step(3.0, 20.0, Action("no_op"))
    congested = loaded.step(3.0, 20.0, Action("no_op"))
    assert congested.delay_ms > empty.delay_ms


# --------------------------------------------------------------------------- #
# Reward and accounting
# --------------------------------------------------------------------------- #

def test_reward_prefers_more_goodput_and_less_loss() -> None:
    better = window_reward(9.0, 10.0, 1.0, 0)
    worse_loss = window_reward(9.0, 10.0, 20.0, 0)
    worse_delay = window_reward(9.0, 60.0, 1.0, 0)
    worse_tput = window_reward(4.0, 10.0, 1.0, 0)
    assert better > worse_loss and better > worse_delay and better > worse_tput


def test_rule_installs_are_charged() -> None:
    assert window_reward(9.0, 10.0, 1.0, 0) > window_reward(9.0, 10.0, 1.0, 1)


def test_oracle_floor_is_zero_below_total_capacity() -> None:
    assert oracle_floor(3.0, 5.0) == pytest.approx(8.0 * TAU_SEC)
    over = oracle_floor(5.0, 40.0)
    assert over == pytest.approx((C_PRIMARY_MBPS + C_ALTERNATE_MBPS) * TAU_SEC)


# --------------------------------------------------------------------------- #
# Optimiser
# --------------------------------------------------------------------------- #

def test_dpp_reroutes_when_the_primary_is_congested_and_the_alternate_is_free() -> None:
    dpp = PipelineDPP()
    weights = {"latency": .25, "throughput": .25, "loss": .25, "energy": .15, "resource": .10}
    action, _, scores = dpp.decide([1.5, 0.0], 3.0, 9.0, 8.0, weights,
                                   ("no_op", "reroute", "rate_limit"))
    assert action.kind == "reroute"
    assert scores["reroute"] < scores["no_op"]


def test_dpp_respects_the_action_mask() -> None:
    dpp = PipelineDPP()
    weights = {"latency": .25, "throughput": .25, "loss": .25, "energy": .15, "resource": .10}
    action, _, scores = dpp.decide([1.5, 0.0], 3.0, 9.0, 8.0, weights, ("no_op", "rate_limit"))
    assert action.kind in ("no_op", "rate_limit")
    assert "reroute" not in scores


def test_dpp_prediction_matches_the_datapath_it_will_drive() -> None:
    """The optimiser's one-slot model must equal the plant's one-slot model."""
    dpp = PipelineDPP()
    for mice, elephant, kind in [(3.0, 9.0, "no_op"), (3.0, 9.0, "reroute"),
                                 (4.0, 14.0, "rate_limit"), (2.0, 1.0, "no_op")]:
        rate = dpp.meter_rate_kbps(mice, elephant) if kind == "rate_limit" else None
        action = Action(kind, rate)
        queue = [0.7, 0.2]
        _, served, lost, delay = dpp._predict(queue, mice, elephant, action)
        datapath = TwoPathDatapath()
        datapath.queue = list(queue)
        outcome = datapath.step(mice, elephant, action)
        assert served == pytest.approx(outcome.served_mbit, abs=1e-12)
        assert lost == pytest.approx(outcome.overflow_mbit + outcome.meter_mbit, abs=1e-12)
        assert delay == pytest.approx(outcome.delay_ms, abs=1e-9)


def test_meter_rate_never_breaches_the_safety_floor() -> None:
    dpp = PipelineDPP()
    for mice in [0.0, 3.0, 8.0, 9.5, 12.0]:
        for elephant in [0.0, 0.1, 5.0, 30.0]:
            assert dpp.meter_rate_kbps(mice, elephant) >= 512


def test_backlog_bound_grows_linearly_in_v() -> None:
    low, high = backlog_bound_mbit(1.0), backlog_bound_mbit(32.0)
    assert high > low
    mid = backlog_bound_mbit(16.5)
    assert mid == pytest.approx((low + high) / 2, rel=1e-9)


# --------------------------------------------------------------------------- #
# Traffic
# --------------------------------------------------------------------------- #

def test_traffic_is_deterministic_per_seed() -> None:
    a = generate_schedule("steady_bursty", 300, 1900)
    b = generate_schedule("steady_bursty", 300, 1900)
    c = generate_schedule("steady_bursty", 300, 1901)
    assert a == b
    assert a != c


def test_demand_series_length_and_nonnegativity() -> None:
    schedule = generate_schedule("steady_bursty", 300, 1900)
    series = demand_series(schedule, 60)
    assert len(series) == 60 * int(round(5.0 / TAU_SEC))
    assert all(m >= 0 and e >= 0 for m, e in series)


# --------------------------------------------------------------------------- #
# Free-tier client
# --------------------------------------------------------------------------- #

def test_paid_openrouter_model_is_refused() -> None:
    with pytest.raises(DeciderError):
        FreeModelDecider(trace_path=Path("nonexistent.jsonl"),
                         primary_model="openai/gpt-4o", fallback_models=[])


def test_free_suffix_is_accepted_and_gemini_entries_pass_through() -> None:
    decider = FreeModelDecider(
        trace_path=Path("nonexistent.jsonl"),
        primary_model="nvidia/nemotron-3.5-lightning:free",
        fallback_models=["gemini:gemini-3.1-flash-lite"])
    assert decider.model_chain == ["openrouter:nvidia/nemotron-3.5-lightning:free",
                                   "gemini:gemini-3.1-flash-lite"]


def test_replay_without_a_trace_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(DeciderError):
        FreeModelDecider(trace_path=tmp_path / "missing.jsonl", mode="replay")


def test_replay_resolves_a_recorded_decision(tmp_path: Path) -> None:
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "usr"}]
    key = prompt_key("action", [], messages)
    trace = tmp_path / "trace.jsonl"
    trace.write_text(json.dumps({
        "key": key, "role": "action", "model_requested": "openrouter:x:free",
        "model_served": "openrouter:x:free", "status": "ok", "elapsed_ms": 1200.0,
        "served_ms": 1100.0, "parsed": {"action": "reroute", "rate_limit_kbps": None,
                                        "reason": "recorded"},
    }) + "\n", encoding="utf-8")
    decider = FreeModelDecider(trace_path=trace, mode="replay")
    record = decider.decide("action", messages, validate_action,
                            {"action": "no_op", "rate_limit_kbps": None, "reason": "fb"})
    assert record.status == "replayed"
    assert record.parsed["action"] == "reroute"


def test_replay_cache_miss_is_an_error_not_a_silent_fallback(tmp_path: Path) -> None:
    trace = tmp_path / "trace.jsonl"
    trace.write_text("", encoding="utf-8")
    decider = FreeModelDecider(trace_path=trace, mode="replay")
    with pytest.raises(DeciderError):
        decider.decide("action", [{"role": "user", "content": "unseen"}],
                       validate_action, {"action": "no_op", "rate_limit_kbps": None,
                                         "reason": "fb"})


def test_enumerate_mode_spends_no_quota_and_counts_prompts(tmp_path: Path) -> None:
    decider = FreeModelDecider(trace_path=tmp_path / "t.jsonl", mode="enumerate")
    for text in ("a", "b", "a"):
        decider.decide("action", [{"role": "user", "content": text}], validate_action,
                       {"action": "no_op", "rate_limit_kbps": None, "reason": "fb"})
    assert decider.live_calls == 0
    assert decider.stats()["uncovered_prompts"] == 2


def test_prompt_key_ignores_the_model_chain() -> None:
    """A recording stays valid when a different free endpoint is available later."""
    messages = [{"role": "user", "content": "x"}]
    assert prompt_key("action", ["a"], messages) == prompt_key("action", ["b"], messages)
    assert prompt_key("action", [], messages) != prompt_key("critique", [], messages)


# --------------------------------------------------------------------------- #
# Response parsing and validation
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("text,expected", [
    ('{"action":"reroute"}', "reroute"),
    ('```json\n{"action": "no_op"}\n```', "no_op"),
    ('Sure! {"action": "rate_limit", "rate_limit_kbps": 4000} hope that helps',
     "rate_limit"),
    ('{"action":"ADMIT"}', "no_op"),
    ('{"action":"throttle","rate_limit_kbps":"3000"}', "rate_limit"),
])
def test_action_parsing_survives_messy_free_model_output(text: str, expected: str) -> None:
    assert validate_action(extract_json_object(text))["action"] == expected


def test_empty_or_unparsable_content_raises() -> None:
    for text in (None, "", "   ", "no json here at all"):
        with pytest.raises(DeciderError):
            extract_json_object(text)


def test_rate_limit_without_a_number_is_rejected() -> None:
    with pytest.raises(DeciderError):
        validate_action({"action": "rate_limit"})


def test_unknown_action_is_rejected() -> None:
    with pytest.raises(DeciderError):
        validate_action({"action": "reboot_the_switch"})


def test_policy_deltas_are_clipped_to_the_declared_range() -> None:
    parsed = validate_policy({"d_v": 99.0, "weight_deltas": {"latency": 5.0, "loss": -9.0},
                              "enable_actions": ["no_op", "reroute", "fly"]})
    assert parsed["d_v"] == 4.0
    assert parsed["weight_deltas"]["latency"] == 0.15
    assert parsed["weight_deltas"]["loss"] == -0.15
    assert parsed["enable_actions"] == ("no_op", "reroute")


def test_critique_falls_back_to_keep_when_the_revision_is_unusable() -> None:
    parsed = validate_critique({"verdict": "revise", "revised_action": {"action": "nonsense"}})
    assert parsed["verdict"] == "keep"
    assert parsed["revised_action"] is None


# --------------------------------------------------------------------------- #
# Controllers
# --------------------------------------------------------------------------- #

def telemetry(mice: float, elephant: float, qp: float = 0.0, qa: float = 0.0) -> Telemetry:
    return Telemetry(window=0, mice_mbps=mice, elephant_mbps=elephant,
                     queue_primary_mbit=qp, queue_alternate_mbit=qa,
                     latency_ms=10.0, loss_pct=0.0, throughput_mbps=mice + elephant,
                     util_primary_pct=10 * (mice + elephant), util_alternate_pct=0.0)


def test_threshold_controller_is_quiet_below_its_trigger() -> None:
    assert threshold_controller(telemetry(3.0, 2.0)).kind == "no_op"


def test_threshold_controller_acts_above_its_trigger() -> None:
    assert threshold_controller(telemetry(3.0, 9.0)).kind in ("reroute", "rate_limit")


def test_tabular_q_is_reproducible_for_a_seed() -> None:
    first = [TabularQController(5).act(telemetry(3.0, 7.0)).kind for _ in range(1)]
    second = [TabularQController(5).act(telemetry(3.0, 7.0)).kind for _ in range(1)]
    assert first == second


def test_telemetry_quantisation_is_idempotent() -> None:
    raw = telemetry(3.14159, 7.77, 0.4321, 0.1234)
    once = raw.quantised()
    assert once.quantised() == once


# --------------------------------------------------------------------------- #
# The reported-results contract
# --------------------------------------------------------------------------- #

STUDY = SELFX_ROOT / "output" / "pipeline_study"
needs_results = pytest.mark.skipif(
    not (STUDY / "pipeline_summary.json").exists(),
    reason="run eval.run_pipeline_study first")


@needs_results
def test_published_run_conserved_bits() -> None:
    summary = json.loads((STUDY / "pipeline_summary.json").read_text(encoding="utf-8"))
    assert summary["max_conservation_error_mbit"] < 1e-9


@needs_results
def test_every_configuration_saw_the_same_offered_traffic() -> None:
    runs = json.loads((STUDY / "pipeline_runs.json").read_text(encoding="utf-8"))
    by_seed: dict = {}
    for run in runs:
        by_seed.setdefault(run["seed"], set()).add(run["traffic_sha256"])
    for seed, digests in by_seed.items():
        assert len(digests) == 1, f"seed {seed} saw {len(digests)} different traces"


@needs_results
def test_llm_statistics_are_reported_not_hidden() -> None:
    summary = json.loads((STUDY / "pipeline_summary.json").read_text(encoding="utf-8"))
    llm = summary["llm"]
    for field in ("served_fraction", "declared_fallbacks", "live_requests",
                  "mean_served_latency_ms", "models_served"):
        assert field in llm
    assert 0.0 <= llm["served_fraction"] <= 1.0


@needs_results
def test_no_openrouter_model_outside_the_free_tier_was_used() -> None:
    summary = json.loads((STUDY / "pipeline_summary.json").read_text(encoding="utf-8"))
    for served in summary["llm"]["models_served"]:
        if served.startswith("openrouter:"):
            assert served.endswith(":free"), f"paid model reached: {served}"
