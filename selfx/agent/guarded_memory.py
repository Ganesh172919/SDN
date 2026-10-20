"""Feasibility-aware numeric retrieval with positive, negative and recent episodes."""
from agent.embedding import cosine, embed_state
from agent.memory import MemoryStore
from eval.simulator import decision_for, reactive_policy


class BalancedMemory(MemoryStore):
    def _prune(self):
        if len(self._records) <= 30:
            return
        ranked = sorted(self._records, key=lambda r: r["reward"])
        selected = self._records[-10:] + ranked[:10] + ranked[-10:]
        by_cycle = {r["cycle"]: r for r in selected}
        self._records = sorted(by_cycle.values(), key=lambda r: r["cycle"])


def guarded_base(summary, demand):
    s = summary["simulation"]
    if s["primary_background_mbps"] + s["elephant_mbps"] <= s["capacity_mbps"]:
        return decision_for("no_op", demand, "Guarded policy: offered primary load fits capacity.")
    return reactive_policy(summary, [], False)


def guarded_policy(net, summary, demand, memory):
    """No simulator outcomes or future demand are used for action selection."""
    base = guarded_base(summary, demand)
    if base.action == "no_op":
        return base, []
    vector = embed_state(summary)
    records = memory.few_shot_examples(k=12, query=summary)
    grouped = {}
    used = []
    for record in records:
        similarity = cosine(vector, embed_state(record["state_summary"]))
        if similarity < .985:
            continue
        candidate = decision_for(record["action"], demand, "Rebuilt from a similar earlier episode")
        if not net.validate(demand, candidate).allowed:
            continue
        weight = similarity ** 12
        grouped.setdefault(record["action"], []).append((record["reward"], weight))
        used.append(record["cycle"])
    scores = {action: sum(r*w for r,w in values)/sum(w for _,w in values) for action,values in grouped.items()}
    if scores:
        selected = max(scores, key=scores.get)
        if scores[selected] > .005 and scores[selected] > scores.get(base.action, 0) + .005:
            return decision_for(selected, demand, "Guarded memory: feasible action with stronger local historical reward"), used
    return base, used
