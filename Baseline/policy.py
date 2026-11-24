from dataclasses import dataclass
from random import Random

from tasf.feedback import Corpus
from tasf.model import TimingCase


@dataclass(frozen=True, slots=True)
class Target:
    template: str
    indices: tuple[int | str, ...]


@dataclass(frozen=True, slots=True)
class Decision:
    state: str
    options: tuple[Target, ...]
    choice: Target


class EditPolicy:
    def select_parent(self, corpus: Corpus, rng: Random) -> TimingCase:
        return corpus.select(rng)

    def choose(self, state: str, options: tuple[Target, ...], rng: Random) -> Target:
        templates = tuple(dict.fromkeys(option.template for option in options))
        template = rng.choice(templates)
        return rng.choice([option for option in options if option.template == template])

    def observe(
        self, parent: TimingCase, candidate: TimingCase, steps: tuple[Decision, ...],
        reward: float, rng: Random,
    ) -> None:
        raise NotImplementedError
