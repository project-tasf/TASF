from collections.abc import Sequence
from math import exp, isfinite
from random import Random

from tasf.feedback.corpus import Corpus
from tasf.model import TimingCase

from .policy import Decision, EditPolicy


class SimulatedAnnealing(EditPolicy):
    def __init__(
        self,
        initial_temperature: float = 1.0,
        cooling: float = 0.98,
        min_temperature: float = 0.01,
        restart_interval: int = 100,
    ):
        if not isfinite(initial_temperature) or initial_temperature <= 0:
            raise ValueError("initial_temperature must be finite and positive")
        if not isfinite(cooling) or not 0 < cooling <= 1:
            raise ValueError("cooling must be in (0, 1]")
        if not isfinite(min_temperature) or not 0 < min_temperature <= initial_temperature:
            raise ValueError("min_temperature must be in (0, initial_temperature]")
        if type(restart_interval) is not int or restart_interval < 1:
            raise ValueError("restart_interval must be a positive integer")
        self.initial_temperature = initial_temperature
        self.cooling = cooling
        self.min_temperature = min_temperature
        self.restart_interval = restart_interval
        self.temperature = initial_temperature
        self.incumbent: TimingCase | None = None
        self.incumbent_reward: float | None = None
        self.rounds_since_restart = 0

    def select_parent(self, corpus: Corpus, rng: Random) -> TimingCase:
        if self.incumbent is None or self.rounds_since_restart >= self.restart_interval:
            self.incumbent = super().select_parent(corpus, rng)
            self.incumbent_reward = None
            self.temperature = self.initial_temperature
            self.rounds_since_restart = 0
        return self.incumbent

    def observe(
        self, parent: TimingCase, candidate: TimingCase, steps: Sequence[Decision],
        reward: float, rng: Random,
    ) -> None:
        if parent != self.incumbent:
            raise ValueError("feedback does not belong to the selected parent")
        previous = self.incumbent_reward
        if (
            previous is None
            or reward >= previous
            or rng.random() < exp((reward - previous) / self.temperature)
        ):
            self.incumbent = candidate
            self.incumbent_reward = reward
        self.temperature = max(self.min_temperature, self.temperature * self.cooling)
        self.rounds_since_restart += 1
