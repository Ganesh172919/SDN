"""Regression checks for neural training, ablation wiring and shared traffic."""
from collections import Counter

from eval.neural_baselines import NeuralController
from eval.run_audited_comparison import (
    ACTIONS, SLOTS_PER_WINDOW, run_episode, safe_action, trace,
)
from eval.pipeline_model import Action


class ModelProbe:
    def __init__(self):
        self.memory_lengths = []

    def action(self, mice, elephant, adapted):
        return ACTIONS.index("reroute" if adapted else "no_op")

    def critique(self, snapshot, proposal, memory):
        self.memory_lengths.append(len(memory))
        return ACTIONS.index("reroute")

    def govern(self, snapshot):
        return "A", {str(i): "A" for i in range(5)}


def test_deep_agents_train_and_evaluate_without_exploration():
    _, series, _ = trace(1000, 10)
    for name, agent_count in (("dqn", 1), ("marl", 2)):
        controller = NeuralController(name, 11)
        run_episode(name, series, neural=controller, training_offset=0)
        evidence = [agent.evidence() for agent in controller.agents]
        assert len(evidence) == agent_count
        assert all(e["initial_sha256"] != e["trained_sha256"] for e in evidence)
        assert all(e["optimizer_steps"] > 0 for e in evidence)
        assert all(e["exploratory_choices"] > 0 for e in evidence)
        run_episode(name, series, neural=controller)
        assert evidence == [agent.evidence() for agent in controller.agents]


def test_ablation_switches_control_execution_and_expose_critique_to_memory():
    _, series, _ = trace(2102, 10)
    model = ModelProbe()
    counters = {
        name: Counter(run_episode(name, series, model)["counts"])
        for name in ("S2", "S4", "S5", "dpp", "no_lora", "no_governor")
    }
    assert model.memory_lengths == [0, 1]
    assert counters["S2"]["critique_revisions"] == 2
    assert counters["S4"]["dpp_decisions"] == len(series) // SLOTS_PER_WINDOW
    assert counters["S5"]["dpp_decisions"] == len(series)
    assert counters["S5"]["policy_changes"] == 1
    assert counters["no_lora"]["lora_proposals"] == 0
    assert counters["no_governor"]["governance_calls"] == 0
    assert counters["dpp"]["dpp_decisions"] == len(series)
    assert counters["dpp"]["lora_proposals"] == counters["dpp"]["governance_calls"] == 0


def test_independent_safety_rejects_infeasible_actions():
    assert safe_action(Action("reroute"), 9.1)[1]
    assert not safe_action(Action("reroute"), 9.0)[1]
    assert safe_action(Action("rate_limit", 7000), 9.0)[1]
    assert not safe_action(Action("rate_limit", 8000), 9.0)[1]

