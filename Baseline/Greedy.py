from collections.abc import Sequence
from random import Random

from tasf.model import TimingCase

from .policy import Decision, EditPolicy, Target


class Greedy(EditPolicy):
    def __init__(self):
        self.counts: dict[str, int] = {}
        self.reward_totals: dict[str, float] = {}

    @property
    def means(self) -> dict[str, float]:
        return {name: self.reward_totals[name] / count for name, count in self.counts.items()}

    def choose(self, state: str, options: Sequence[Target], rng: Random) -> Target:
        by_template: dict[str, list[Target]] = {}
        for option in options:
            by_template.setdefault(option.template, []).append(option)
        if not by_template:
            raise ValueError("no legal targets are available")
        preferred = [name for name in by_template if name not in self.counts]
        if not preferred:
            means = {name: self.reward_totals[name] / self.counts[name] for name in by_template}
            best = max(means.values())
            preferred = [name for name, mean in means.items() if mean == best]
        return rng.choice(by_template[rng.choice(preferred)])

    def observe(
        self, parent: TimingCase, candidate: TimingCase, steps: Sequence[Decision],
        reward: float, rng: Random,
    ) -> None:
        for name in dict.fromkeys(step.choice.template for step in steps):
            self.counts[name] = self.counts.get(name, 0) + 1
            self.reward_totals[name] = self.reward_totals.get(name, 0) + reward
