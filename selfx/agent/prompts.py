"""
Phase 3/4 — prompt templates.

Two prompts:
  1. DECIDE_SYSTEM_PROMPT + build_decide_messages(...)   — observe -> decide
  2. REFLECT_SYSTEM_PROMPT + build_reflect_messages(...) — act -> reflect

Both are plain LangChain message lists (system + human) so they drop
straight into `llm.invoke(messages)` / `structured_llm.invoke(messages)`.
"""

import json

DECIDE_SYSTEM_PROMPT = """You are the decision-making core of a self-improving \
SDN flow-management agent. Every control-loop cycle you are shown the \
current network state (per-flow and per-port OpenFlow counters) and a \
handful of your own best past (state, action, outcome, reflection) \
examples. You must choose EXACTLY ONE of three actions:

  - "reroute":    move a flow to a different output port to avoid a \
congested link. Requires target_dpid, target_flow_match, reroute_out_port.
  - "rate_limit": cap a flow's rate via an OpenFlow meter to protect a \
shared link. Requires target_dpid, target_flow_match, rate_limit_kbps.
  - "no_op":      do nothing this cycle, e.g. the network is healthy or \
you are not confident an action would help.

A separate, hard-coded safety check will reject rate_limit or reroute \
actions that are too aggressive (e.g. dropping too much of a flow's \
traffic, or overloading the target link) and silently fall back to \
no_op — so prefer a moderate, defensible action over an extreme one. \
Always give a one-line rationale. Return ONLY the requested structured \
output, nothing else."""

REFLECT_SYSTEM_PROMPT = """You just took one action in a self-improving \
SDN flow-management loop and observed the outcome one window later. \
Write a single, concise sentence reflecting on whether the action \
helped, hurt, or was neutral, and why — this reflection will be stored \
alongside the (state, action, outcome) record and shown to your future \
self as a few-shot example, so make it something you'd actually find \
useful to read again."""


def _format_example(record: dict) -> str:
    return (
        f"- state: {json.dumps(record['state_summary'])}\n"
        f"  action: {record['action']} params={json.dumps(record['params'])}\n"
        f"  reward: {record['reward']:.3f}\n"
        f"  reflection: {record['reflection']}"
    )


def build_decide_messages(state_summary: dict, few_shot_examples: list[dict]) -> list[dict]:
    examples_block = (
        "\n".join(_format_example(r) for r in few_shot_examples)
        if few_shot_examples
        else "(no memory yet — this is one of the first cycles)"
    )
    human = (
        f"Your best past examples (highest reward first):\n{examples_block}\n\n"
        f"Current network state:\n{json.dumps(state_summary, indent=2)}\n\n"
        "Choose one action for this cycle."
    )
    return [
        {"role": "system", "content": DECIDE_SYSTEM_PROMPT},
        {"role": "user", "content": human},
    ]


def build_reflect_messages(state_summary: dict, action: str, params: dict,
                            outcome_metrics: dict, reward: float) -> list[dict]:
    human = (
        f"State when you decided: {json.dumps(state_summary)}\n"
        f"Action taken: {action} params={json.dumps(params)}\n"
        f"Outcome one window later: {json.dumps(outcome_metrics)}\n"
        f"Computed reward: {reward:.3f}\n\n"
        "Write your one-sentence reflection."
    )
    return [
        {"role": "system", "content": REFLECT_SYSTEM_PROMPT},
        {"role": "user", "content": human},
    ]
