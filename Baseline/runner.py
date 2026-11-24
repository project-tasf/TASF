from collections.abc import Callable, Iterable, Iterator
from itertools import islice

from tasf.benches import Testbench
from tasf.campaign import RoundResult, Settings
from tasf.campaign.execution import CampaignExecution
from tasf.campaign.planner import case_id
from tasf.model import Profile, TimingCase
from tasf.observation import ReferenceModel

from .Greedy import Greedy
from .Random import RandomTesting
from .SA import SimulatedAnnealing
from .SD_SAC import SDSAC
from .neighborhood import Neighborhood
from .policy import EditPolicy


BASELINES = {
    "Random": RandomTesting,
    "Greedy": Greedy,
    "SA": SimulatedAnnealing,
    "SD-SAC": SDSAC,
}


class BaselineCampaign(CampaignExecution):
    def __init__(
        self, method: RandomTesting | EditPolicy, bench_factory: Callable[[], Testbench],
        reference_factory: Callable[[], ReferenceModel], *, settings: Settings = Settings(),
        profile: Profile = Profile(), accepts: Callable[[TimingCase], bool] | None = None,
        templates: Iterable[str] | None = None,
    ):
        super().__init__(bench_factory, reference_factory, settings, profile, accepts)
        self.method = method
        self.neighborhood = Neighborhood(profile, self.accepts, templates) if isinstance(method, EditPolicy) else None
        self.next_round = 1

    def rounds(self) -> Iterator[RoundResult]:
        if not len(self.corpus):
            raise ValueError("At least one calibrated seed is required")
        while True:
            number = self.next_round
            self.next_round += 1
            if isinstance(self.method, RandomTesting):
                candidate = self.method.propose(self.profile, self.accepts, self.rng)
                if candidate is None:
                    yield RoundResult(number, "baseline", "", (), "generation_failed")
                else:
                    yield self._evaluate(candidate, number, "baseline", ())
                continue
            parent = self.method.select_parent(self.corpus, self.rng)
            candidate, steps = self.neighborhood.propose(
                parent, self.method, self.rng, self.settings.protected_prefix,
            )
            if not steps:
                yield RoundResult(number, "baseline", case_id(parent), (), "no_edit", reward=0)
                continue
            retained = tuple(step.choice.template for step in steps)
            result = self._evaluate(candidate, number, "baseline", retained)
            if result.reward is not None:
                self.method.observe(parent, candidate, steps, result.reward, self.rng)
            yield result

    def run(self, rounds: int | None = None) -> tuple[RoundResult, ...]:
        if rounds is None:
            settings = self.settings
            rounds = settings.cycles * (settings.training_rounds + settings.evaluation_rounds)
            if self.next_round == 1:
                rounds += settings.warmup_training + settings.warmup_evaluation
        if type(rounds) is not int or rounds < 0:
            raise ValueError("The round limit must be a nonnegative integer")
        return tuple(islice(self.rounds(), rounds))
