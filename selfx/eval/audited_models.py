"""Local model execution for the audited pipeline, with constrained outputs."""
from collections import Counter, deque
import torch

from agent.self_improvement.policy import ACTIONS, LoRAPolicy

ROLE_PROMPTS = {
    "flow sizing": "Decide whether burst size calls for short queues or lower switching cost.",
    "routing": "Decide whether alternate-path use is worth its added delay and cost.",
    "congestion": "Decide how urgently the current queues need to drain.",
    "safety": "Decide how strongly to prioritise avoiding loss under the current demand.",
    "service": "Decide how to balance delay-sensitive background traffic and bulk goodput.",
}
OBJECTIVES = {
    "A": (-2.0, {"latency": 0.06, "loss": 0.06, "energy": -0.07, "resource": -0.05}),
    "B": (0.0, {}),
    "C": (2.0, {"latency": -0.06, "loss": -0.06, "energy": 0.07, "resource": 0.05}),
}


class LocalModels:
    def __init__(self, adapter):
        self.policy = LoRAPolicy(candidate=str(adapter), threads=2)
        if self.policy.fractions["candidate"] != 1.0:
            raise ValueError("The audited LoRA arm requires full adapter deployment")
        self.actions = {}
        self.answers = {}
        self.forward_batches = Counter()

    def action(self, mice, elephant, adapted):
        mice, elephant = round(mice * 2) / 2, round(elephant * 2) / 2
        key = mice, elephant, adapted
        if key not in self.actions:
            observation = {
                "capacity_mbps": 10.0,
                "primary_background_mbps": mice,
                "alternate_background_mbps": 0.0,
                "elephant_mbps": elephant,
            }
            role = "candidate" if adapted else "base"
            result = self.policy.predict([observation], role)[0]
            if result["adapter_used"] != adapted:
                raise AssertionError("Unexpected adapter state")
            self.actions[key] = ACTIONS.index(result["action"])
            self.forward_batches["adapter" if adapted else "base"] += 1
        return self.actions[key]

    @torch.inference_mode()
    def tokens(self, prompts, component):
        missing = list(dict.fromkeys(prompt for prompt in prompts if prompt not in self.answers))
        if missing:
            batch = self.policy.tokenizer(missing, padding=True, return_tensors="pt")
            with self.policy.model.disable_adapter():
                scores = self.policy.model(**batch, logits_to_keep=1).logits[:, -1, self.policy.code_ids]
            if not torch.isfinite(scores).all():
                raise ValueError("Non-finite local model logits")
            self.answers.update(zip(missing, ("ABC"[int(i)] for i in scores.argmax(-1))))
            self.forward_batches[component] += 1
        return [self.answers[prompt] for prompt in prompts]

    def critique(self, snapshot, proposal, memory):
        if memory:
            history = " ".join(
                f"{ACTIONS[a]} reward {r:+.1f}." for a, r in memory
            )
        else:
            history = "No completed windows."
        prompt = (
            f"SDN policy review. {snapshot}\nPrevious outcomes: {history}\n"
            f"Proposed action: {ACTIONS[proposal]}. Review using previous rewards and current load.\n"
            "A=keep on primary, B=move to alternate, C=bound the flow with a primary meter.\n"
            "Best action after review:"
        )
        return "ABC".index(self.tokens([prompt], "critique")[0])

    def govern(self, snapshot):
        choices = (
            "A=reduce queues and loss, B=keep policy unchanged, C=prioritise operating cost. "
            "Select the best policy adjustment.\nAdjustment:"
        )
        # Each specialist has its own prompt and completion, batched in one forward pass.
        roles = tuple(ROLE_PROMPTS)
        prompts = [f"SDN {role} specialist. {ROLE_PROMPTS[role]}\n{snapshot}\n{choices}"
                   for role in roles]
        ballots = dict(zip(roles, self.tokens(prompts, "specialists")))
        advice = ", ".join(f"{role}={ballot}" for role, ballot in ballots.items())
        merged = self.tokens(
            [f"SDN orchestrator. Reconcile specialist recommendations: {advice}.\n"
             f"{snapshot}\n{choices}"], "orchestrator",
        )[0]
        return merged, ballots


def snapshot(mice, elephant, queue):
    return (f"Primary background {mice:.0f} Mbps; bulk flow {elephant:.0f} Mbps; "
            f"primary queue {queue[0]:.0f} and alternate queue {queue[1]:.0f} Mbit. "
            "Each link carries at most 10 Mbps.")


def episodic_memory():
    return deque(maxlen=3)

