from __future__ import annotations

from collections import Counter, defaultdict, deque
from collections.abc import Iterable
from itertools import combinations
from math import ceil, isfinite, log, sqrt
from random import Random
from statistics import fmean
from typing import Protocol


class Template(Protocol):
    name: str
    family: str


Observation = tuple[Iterable[str], Iterable[str], float]


class CMAB:
    def __init__(
        self,
        rho: float = 0.5,
        beta: float = 0.5,
        quota: int = 2,
        window: int = 10,
        co_weight: float = 1.0,
        alpha: float = 0.2,
    ):
        if not 0 <= rho <= 1 or not 0 < beta <= 1 or not 0 < alpha <= 1:
            raise ValueError("Invalid CMAB mixing, retention or update rate")
        if window < 1 or quota < 0 or not isfinite(co_weight) or co_weight < 0:
            raise ValueError("Invalid CMAB window, family quota or pair weight")
        self.rho = rho
        self.beta = beta
        self.quota = quota
        self.window = window
        self.co_weight = co_weight
        self.alpha = alpha
        self.cycles = 0
        self.history: dict[str, deque[float]] = {}
        self.pairs: dict[tuple[str, str], float] = {}

    def _pick(self, names: list[str], selected: tuple[str, ...], rng: Random) -> str:
        unseen = [name for name in names if name not in self.history]
        if unseen:
            return rng.choice(unseen)
        scores = {}
        for name in names:
            history = self.history[name]
            exploration = sqrt(3 * log(max(2, self.cycles + 1)) / (2 * len(history)))
            pair_mean = 0.0
            if selected:
                pair_mean = fmean(
                    self.pairs.get(tuple(sorted((name, other))), 0.0)
                    for other in selected
                )
            utility = fmean(history) + self.co_weight * pair_mean
            scores[name] = (1 - self.rho) * utility + self.rho * exploration
        best = max(scores.values())
        return rng.choice([name for name in names if scores[name] == best])

    def screen(self, templates: Iterable[Template], rng: Random) -> tuple[str, ...]:
        families = {}
        for template in templates:
            if template.name in families:
                raise ValueError("Template names must be unique")
            families[template.name] = template.family
        capacities = Counter(families.values())
        required = {family: min(self.quota, count) for family, count in capacities.items()}
        target = max(ceil(self.beta * len(families)), sum(required.values()))
        selected = []
        available = sorted(families)
        while len(selected) < target:
            candidates = available
            if target - len(selected) == sum(required.values()):
                candidates = [name for name in available if required[families[name]] > 0]
            name = self._pick(candidates, tuple(selected), rng)
            family = families[name]
            required[family] = max(0, required[family] - 1)
            selected.append(name)
            available.remove(name)
        return tuple(selected)

    def supplement(
        self, legal_templates: Iterable[Template], selected: Iterable[str], rng: Random
    ) -> str | None:
        selected = tuple(dict.fromkeys(selected))
        candidates = sorted({item.name for item in legal_templates}.difference(selected))
        return self._pick(candidates, selected, rng) if candidates else None

    def update(self, selected: tuple[str, ...], reward: float) -> None:
        self.update_cycle(((selected, selected, reward),))

    def update_cycle(
        self, observations: Iterable[Observation], eligible: Iterable[str] | None = None
    ) -> None:
        eligible_names = None if eligible is None else set(eligible)
        returns: dict[str, list[float]] = defaultdict(list)
        pairs = self.pairs.copy()
        for attempted, retained, reward in observations:
            attempted_names, retained_names = set(attempted), set(retained)
            if not isfinite(reward) or not retained_names.issubset(attempted_names):
                raise ValueError("Invalid reward or retained template outside attempted set")
            observed = attempted_names if eligible_names is None else attempted_names & eligible_names
            for name in observed:
                returns[name].append(reward if name in retained_names else 0.0)
            pairs = {pair: (1 - self.alpha) * weight for pair, weight in pairs.items()}
            if reward:
                for pair in combinations(sorted(retained_names), 2):
                    pairs[pair] = pairs.get(pair, 0.0) + self.alpha * reward
        averages = {name: fmean(values) for name, values in returns.items()}
        for name, value in averages.items():
            if name not in self.history:
                self.history[name] = deque(maxlen=self.window)
            self.history[name].append(value)
        self.pairs = pairs
        self.cycles += 1
