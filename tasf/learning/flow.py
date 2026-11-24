from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import exp, fsum, isfinite, log
from random import Random
from typing import Protocol, TypeVar


class Action(Protocol):
    key: str
    template: str


ActionType = TypeVar("ActionType", bound=Action)


@dataclass(frozen=True, slots=True)
class FlowStep:
    state: str
    keys: tuple[str, ...]
    templates: tuple[str, ...]
    choice: int


class GFlowPolicy:
    def __init__(self, learning_rate: float = 0.01, reward_floor: float = 1e-6):
        if not isfinite(learning_rate) or learning_rate <= 0:
            raise ValueError("Learning rate must be finite and positive")
        if not isfinite(reward_floor) or reward_floor <= 0:
            raise ValueError("Reward floor must be finite and positive")
        self.learning_rate = learning_rate
        self.reward_floor = reward_floor
        self.log_normalizers: dict[str, float] = {}
        self.state_logits: dict[tuple[str, str], float] = {}
        self.template_logits: dict[str, float] = {}

    def _log_probs(
        self, state: str, keys: tuple[str, ...], templates: tuple[str, ...]
    ) -> tuple[float, ...]:
        logits = [
            self.state_logits.get((state, key), 0.0) + self.template_logits.get(template, 0.0)
            for key, template in zip(keys, templates, strict=True)
        ]
        peak = max(logits)
        offsets = [value - peak for value in logits]
        log_sum = log(fsum(exp(value) for value in offsets))
        return tuple(value - log_sum for value in offsets)

    def choose(
        self, state: str, actions: Sequence[ActionType], rng: Random, epsilon: float = 0.6
    ) -> tuple[ActionType, FlowStep]:
        if not actions or not 0 <= epsilon <= 1:
            raise ValueError("Choose requires legal actions and an epsilon in [0, 1]")
        keys = tuple(action.key for action in actions)
        if len(set(keys)) != len(keys):
            raise ValueError("Legal action keys must be unique within a state")
        templates = tuple(action.template for action in actions)
        counts = Counter(templates)
        learned = self._log_probs(state, keys, templates)
        weights = [
            (1 - epsilon) * exp(log_prob) + epsilon / (len(counts) * counts[template])
            for template, log_prob in zip(templates, learned, strict=True)
        ]
        choice = rng.choices(range(len(keys)), weights=weights, k=1)[0]
        return actions[choice], FlowStep(state, keys, templates, choice)

    def learn(
        self, steps: Iterable[FlowStep], reward: float, *, context: str | None = None
    ) -> float:
        if not isfinite(reward) or reward < 0:
            raise ValueError("Trajectory reward must be finite and nonnegative")
        path = tuple(steps)
        if context is None:
            if not path:
                raise ValueError("An empty trajectory requires an initial context")
            context = path[0].state
        residual = self.log_normalizers.get(context, 0.0) - log(reward + self.reward_floor)
        state_gradient: dict[tuple[str, str], float] = defaultdict(float)
        template_gradient: dict[str, float] = defaultdict(float)
        for step in path:
            if not 0 <= step.choice < len(step.keys) or len(set(step.keys)) != len(step.keys):
                raise ValueError("Invalid trajectory action index or duplicate key")
            probs = self._log_probs(step.state, step.keys, step.templates)
            residual += probs[step.choice]
            for index, (key, template, lp) in enumerate(
                zip(step.keys, step.templates, probs, strict=True)
            ):
                difference = float(index == step.choice) - exp(lp)
                state_gradient[step.state, key] += difference
                template_gradient[template] += difference
        update = 2 * self.learning_rate * residual
        self.log_normalizers[context] = self.log_normalizers.get(context, 0.0) - update
        for pair, gradient in state_gradient.items():
            self.state_logits[pair] = self.state_logits.get(pair, 0.0) - update * gradient
        for template, gradient in template_gradient.items():
            self.template_logits[template] = self.template_logits.get(template, 0.0) - update * gradient
        return residual * residual
