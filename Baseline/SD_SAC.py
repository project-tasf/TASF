from collections import deque
from dataclasses import dataclass
from math import exp, fsum, isfinite, log
from random import Random

from tasf.model import TimingCase

from .policy import Decision, EditPolicy, Target


@dataclass(slots=True)
class _Critics:
    values: tuple[float, float]
    targets: tuple[float, float]
    synced_at: int

    def sync(self, tick: int, target_rate: float) -> None:
        elapsed = tick - self.synced_at
        if elapsed:
            retention = (1.0 - target_rate) ** elapsed
            self.targets = tuple(
                retention * old + (1.0 - retention) * new
                for old, new in zip(self.targets, self.values)
            )
            self.synced_at = tick


@dataclass(frozen=True, slots=True)
class _Transition:
    decision: Decision
    successor: Decision | None
    reward: float
    behavior_entropy: float


class SDSAC(EditPolicy):
    def __init__(
        self,
        *,
        discount: float = 0.99,
        critic_rate: float = 0.15,
        actor_rate: float = 0.12,
        target_rate: float = 0.05,
        q_clip: float = 0.5,
        entropy_penalty: float = 0.5,
        temperature: float = 0.2,
        temperature_rate: float = 0.005,
        target_entropy_fraction: float = 0.8,
        replay_capacity: int = 2048,
        replay_updates: int = 4,
    ) -> None:
        if not 0 <= discount <= 1 or not 0 < critic_rate <= 1 or not 0 < target_rate <= 1:
            raise ValueError("Discount and critic or target rates must be in range.")
        if not all(isfinite(x) and x > 0 for x in (q_clip, actor_rate, temperature)):
            raise ValueError("Clip range, actor rate, and temperature must be positive and finite.")
        if not all(isfinite(x) and x >= 0 for x in (entropy_penalty, temperature_rate)):
            raise ValueError("Entropy penalty and temperature rate must be nonnegative and finite.")
        if not 0 <= target_entropy_fraction <= 1 or replay_capacity < 1 or replay_updates < 0:
            raise ValueError("Invalid entropy target or replay settings.")
        self.discount = discount
        self.critic_rate = critic_rate
        self.actor_rate = actor_rate
        self.target_rate = target_rate
        self.q_clip = q_clip
        self.entropy_penalty = entropy_penalty
        self.log_temperature = log(temperature)
        self.temperature_rate = temperature_rate
        self.target_entropy_fraction = target_entropy_fraction
        self.replay_updates = replay_updates
        self.replay: deque[_Transition] = deque(maxlen=replay_capacity)
        self.logits: dict[tuple[str, Target], float] = {}
        self.critics: dict[tuple[str, Target], _Critics] = {}
        self.updates = 0

    def _distribution(
        self, state: str, options: tuple[Target, ...]
    ) -> tuple[list[float], list[float], float]:
        if not options:
            raise ValueError("At least one legal action is required.")
        logits = [self.logits.get((state, option), 0.0) for option in options]
        maximum = max(logits)
        centered = [value - maximum for value in logits]
        normalizer = log(fsum(exp(value) for value in centered))
        log_probs = [value - normalizer for value in centered]
        probs = [exp(value) for value in log_probs]
        entropy = -fsum(p * lp for p, lp in zip(probs, log_probs))
        return probs, log_probs, entropy

    def choose(self, state: str, options: tuple[Target, ...], rng: Random) -> Target:
        probs, _, _ = self._distribution(state, options)
        return rng.choices(options, weights=probs, k=1)[0]

    def _mean_q(self, state: str, option: Target, *, lagged: bool) -> float:
        pair = self.critics.get((state, option))
        if pair is None:
            return 0.0
        if lagged:
            pair.sync(self.updates, self.target_rate)
            first, second = pair.targets
        else:
            first, second = pair.values
        return 0.5 * first + 0.5 * second

    def _critic_update(self, value: float, lagged: float, target: float) -> float:
        shift = value - lagged
        clipped = lagged + max(-self.q_clip, min(self.q_clip, shift))
        if abs(shift) > self.q_clip and abs(clipped - target) > abs(value - target):
            return value
        return value + self.critic_rate * (target - value)

    def _train(self, transition: _Transition, rng: Random) -> None:
        decision = transition.decision
        successor = transition.successor
        temperature = exp(self.log_temperature)
        target = transition.reward
        if successor is not None:
            probs, _, entropy = self._distribution(successor.state, successor.options)
            expected_q = fsum(
                p * self._mean_q(successor.state, option, lagged=True)
                for option, p in zip(successor.options, probs)
            )
            target += self.discount * (expected_q + temperature * entropy)

        key = (decision.state, decision.choice)
        pair = self.critics.get(key)
        if pair is None:
            initial = (rng.uniform(-0.01, 0.01), rng.uniform(-0.01, 0.01))
            pair = self.critics[key] = _Critics(initial, initial, self.updates)
        pair.sync(self.updates, self.target_rate)
        pair.values = tuple(
            self._critic_update(value, lagged, target)
            for value, lagged in zip(pair.values, pair.targets)
        )

        probs, log_probs, entropy = self._distribution(decision.state, decision.options)
        values = [self._mean_q(decision.state, option, lagged=False) for option in decision.options]
        expected_q = fsum(p * q for p, q in zip(probs, values))
        entropy_weight = temperature - 2.0 * self.entropy_penalty * (entropy - transition.behavior_entropy)
        for option, p, lp, q in zip(decision.options, probs, log_probs, values):
            gradient = p * (q - expected_q + entropy_weight * (-lp - entropy))
            key = (decision.state, option)
            self.logits[key] = self.logits.get(key, 0.0) + self.actor_rate * gradient

        if self.temperature_rate:
            wanted_entropy = self.target_entropy_fraction * log(len(decision.options))
            updated = self.log_temperature + self.temperature_rate * (wanted_entropy - entropy)
            self.log_temperature = max(-12.0, min(5.0, updated))
        self.updates += 1

    def observe(
        self,
        parent: TimingCase,
        candidate: TimingCase,
        steps: tuple[Decision, ...],
        reward: float,
        rng: Random,
    ) -> None:
        if not isfinite(reward):
            raise ValueError("Reward must be finite.")
        transitions = []
        for i, decision in enumerate(steps):
            if decision.choice not in decision.options:
                raise ValueError("Chosen edit is outside its legal action set.")
            successor = steps[i + 1] if i + 1 < len(steps) else None
            _, _, entropy = self._distribution(decision.state, decision.options)
            transitions.append(_Transition(decision, successor, reward if successor is None else 0.0, entropy))
        if not transitions:
            return
        self.replay.extend(transitions)
        for transition in reversed(transitions):
            self._train(transition, rng)
        for transition in rng.sample(self.replay, min(self.replay_updates, len(self.replay))):
            self._train(transition, rng)

