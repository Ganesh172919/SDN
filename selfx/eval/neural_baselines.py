"""Train neural value-based reference policies for the audited SELF-X study."""
from collections import deque
from copy import deepcopy
from hashlib import sha256
import random

import torch
from torch import nn

from eval.pipeline_model import Action, PipelineDPP

ACTIONS = ("no_op", "reroute", "rate_limit")
HIDDEN = 64
BATCH = 64
GAMMA = 0.97


def action_for(index, mice, elephant, origin):
    kind = ACTIONS[index]
    rate = PipelineDPP.meter_rate_kbps(mice, elephant) if kind == "rate_limit" else None
    return Action(kind, rate, origin)


def observation(mice, elephant, queue, previous):
    return (
        mice / 10, elephant / 20, queue[0] / 2, queue[1] / 2,
        *(float(previous.kind == action) for action in ACTIONS),
    )


def parameter_hash(model):
    digest = sha256()
    for parameter in model.parameters():
        digest.update(parameter.detach().numpy().tobytes())
    return digest.hexdigest()


class QAgent:
    def __init__(self, size, seed):
        self.rng = random.Random(seed)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            self.online = nn.Sequential(
                nn.Linear(7, HIDDEN), nn.ReLU(), nn.Linear(HIDDEN, HIDDEN),
                nn.ReLU(), nn.Linear(HIDDEN, size),
            )
        self.target = deepcopy(self.online).requires_grad_(False)
        self.optimizer = torch.optim.Adam(self.online.parameters(), lr=0.001)
        self.replay = deque(maxlen=20_000)
        self.size = size
        self.updates = 0
        self.target_syncs = 0
        self.exploratory_choices = 0
        self.action_counts = [0] * size
        self.last_loss = None
        self.initial_hash = parameter_hash(self.online)

    @torch.inference_mode()
    def choose(self, state, epsilon):
        if epsilon and self.rng.random() < epsilon:
            self.exploratory_choices += 1
            return self.rng.randrange(self.size)
        return int(self.online(torch.tensor(state, dtype=torch.float32)).argmax())

    def observe(self, state, action, reward, next_state, terminal, step):
        self.action_counts[action] += 1
        self.replay.append((state, action, reward, next_state, terminal))
        if len(self.replay) < BATCH or step % 8:
            return
        states, actions, rewards, following, done = zip(*self.rng.sample(self.replay, BATCH))
        estimate = self.online(torch.tensor(states)).gather(1, torch.tensor(actions)[:, None]).squeeze(1)
        with torch.no_grad():
            future = self.target(torch.tensor(following)).max(dim=1).values
            target = torch.tensor(rewards) + GAMMA * future * (~torch.tensor(done))
        loss = nn.functional.smooth_l1_loss(estimate, target)
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.online.parameters(), 10.0)
        self.optimizer.step()
        self.last_loss = float(loss.detach())
        self.updates += 1
        if self.updates % 100 == 0:
            self.target.load_state_dict(self.online.state_dict())
            self.target_syncs += 1

    def evidence(self):
        return {
            "initial_sha256": self.initial_hash,
            "trained_sha256": parameter_hash(self.online),
            "optimizer_steps": self.updates,
            "target_syncs": self.target_syncs,
            "exploratory_choices": self.exploratory_choices,
            "training_actions": self.action_counts,
            "final_training_loss": self.last_loss,
        }


class NeuralController:
    """Single DQN or two independently trained DQNs with a shared team reward.

    In the two-agent controller, agent 0 selects the path and agent 1 selects
    metering on the primary path. Alternate routing takes precedence over the
    meter vote, keeping the joint action space identical to single-agent DQN.
    """

    def __init__(self, name, seed):
        self.name = name
        self.agents = (
            (QAgent(3, seed),) if name == "dqn"
            else (QAgent(2, seed), QAgent(2, seed + 1))
        )

    def choose(self, state, epsilon=0.0):
        choices = tuple(agent.choose(state, epsilon) for agent in self.agents)
        if len(choices) == 1:
            return choices[0], choices
        route, meter = choices
        return (1 if route else 2 if meter else 0), choices

    def observe(self, state, choices, reward, next_state, terminal, step):
        for agent, choice in zip(self.agents, choices):
            agent.observe(state, choice, reward, next_state, terminal, step)

