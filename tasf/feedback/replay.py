from collections import deque
from dataclasses import dataclass
from math import isfinite
from random import Random

from ..learning import FlowStep


@dataclass(frozen=True, slots=True)
class ReplayRecord:
    context: str
    steps: tuple[FlowStep, ...]
    reward: float


class ReplayBuffer:
    def __init__(self, capacity: int):
        if capacity < 1:
            raise ValueError("Replay capacity must be positive")
        self._records: deque[ReplayRecord] = deque(maxlen=capacity)

    def __len__(self) -> int:
        return len(self._records)

    def append(self, context: str, steps: tuple[FlowStep, ...], reward: float) -> None:
        if not isfinite(reward) or reward < 0:
            raise ValueError("Replay reward must be finite and nonnegative")
        self._records.append(ReplayRecord(context, tuple(steps), reward))

    def sample(self, rng: Random) -> ReplayRecord:
        if not self._records:
            raise LookupError("No training trajectories have been recorded")
        return self._records[rng.randrange(len(self._records))]
