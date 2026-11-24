from collections import deque
from dataclasses import dataclass
from random import Random

from ..model import TimingCase
from ..observation import Feature, Observation


@dataclass(frozen=True, slots=True)
class Feedback:
    reward: int
    added: bool
    novel: frozenset[Feature]


class Corpus:
    def __init__(self, capacity: int = 1024):
        if capacity < 1:
            raise ValueError("Corpus capacity must be positive")
        self.capacity = capacity
        self._coverage: set[Feature] = set()
        self._seeds: list[TimingCase] = []
        self._generated: deque[TimingCase] = deque()
        self._retained: set[TimingCase] = set()

    def __len__(self) -> int:
        return len(self._retained)

    @property
    def coverage(self) -> frozenset[Feature]:
        return frozenset(self._coverage)

    def _evict(self) -> None:
        self._retained.remove(self._generated.popleft())

    def admit_seed(self, case: TimingCase, observation: Observation) -> None:
        if not observation.trace.completed or observation.discrepancies:
            raise ValueError("Seed calibration needs a complete, matching execution")
        if case not in self._retained:
            if len(self) == self.capacity:
                if not self._generated:
                    raise ValueError("Corpus capacity is exhausted by calibrated seeds")
                self._evict()
            self._seeds.append(case)
            self._retained.add(case)
        elif case in self._generated:
            self._generated.remove(case)
            self._seeds.append(case)
        self._coverage.update(observation.features)

    def record(self, case: TimingCase, observation: Observation) -> Feedback:
        if not observation.trace.completed:
            return Feedback(0, False, frozenset())
        novel = observation.features.difference(self._coverage)
        if not novel:
            return Feedback(0, False, novel)
        added = case not in self._retained and len(self._seeds) < self.capacity
        if added:
            if len(self) == self.capacity:
                self._evict()
            self._generated.append(case)
            self._retained.add(case)
        self._coverage.update(novel)
        return Feedback(1, added, novel)

    def select(self, rng: Random) -> TimingCase:
        if not self._retained:
            raise LookupError("No timing cases have been retained")
        index = rng.randrange(len(self))
        if index < len(self._seeds):
            return self._seeds[index]
        return self._generated[index - len(self._seeds)]
