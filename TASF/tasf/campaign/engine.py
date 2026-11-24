from collections.abc import Callable, Iterable
from dataclasses import dataclass
from random import Random

from ..benches import Testbench
from ..feedback import Corpus, ReplayBuffer
from ..generation import validate
from ..learning import CMAB, GFlowPolicy
from ..model import Profile, TimingCase
from ..observation import Discrepancy, Observer, ReferenceModel
from .planner import Planner, case_id
from .settings import Settings


@dataclass(frozen=True, slots=True)
class RoundResult:
    cycle: int
    phase: str
    case_id: str
    templates: tuple[str, ...]
    status: str
    reward: int | None = None
    new_features: int = 0
    added: bool = False
    discrepancies: tuple[Discrepancy, ...] = ()
    replay_confirmed: bool | None = None
    detail: str = ""


class Campaign:
    def __init__(
        self,
        bench_factory: Callable[[], Testbench],
        reference_factory: Callable[[], ReferenceModel],
        *,
        settings: Settings = Settings(),
        profile: Profile = Profile(),
        accepts: Callable[[TimingCase], bool] | None = None,
        templates: Iterable[str] | None = None,
        bandit: CMAB | None = None,
        policy: GFlowPolicy | None = None,
    ):
        self.settings = settings
        self.profile = profile
        self.bench_factory = bench_factory
        self.reference_factory = reference_factory
        self.accepts = accepts if accepts is not None else lambda case: True
        self.rng = Random(settings.random_seed)
        self.bandit = bandit if bandit is not None else CMAB()
        self.policy = policy if policy is not None else GFlowPolicy()
        self.planner = Planner(profile, self.bandit, self.policy, self.accepts, templates)
        self.corpus = Corpus()
        self.replay = ReplayBuffer(settings.replay_capacity)
        self.completed_cycles = 0
        self.warmed_up = False

    def _observe(self, case: TimingCase):
        observer = Observer(self.bench_factory(), self.reference_factory())
        return observer.run(case, self.settings.max_cycles)

    def calibrate(self, seeds: Iterable[TimingCase]) -> None:
        for case in seeds:
            validate(case, self.profile)
            if not self.accepts(case):
                raise ValueError("Calibration case violates the IP constraints")
            observation = self._observe(case)
            self.corpus.admit_seed(case, observation)

    def _round(self, cycle, phase, scope, epsilon):
        parent = self.corpus.select(self.rng)
        proposal = self.planner.propose(parent, scope, self.rng, epsilon, self.settings.protected_prefix)
        case = proposal.case
        fields = (cycle, phase, case_id(case), proposal.templates)
        if not proposal.steps:
            result = RoundResult(*fields, "no_edit", reward=0)
        else:
            try:
                observation = self._observe(case)
            except (OSError, TypeError, ValueError) as error:
                return RoundResult(*fields, "execution_error", detail=str(error))
            if not observation.trace.completed:
                return RoundResult(*fields, "cycle_limit")
            feedback = self.corpus.record(case, observation)
            confirmed = None
            detail = ""
            if observation.discrepancies:
                try:
                    replayed = self._observe(case)
                    confirmed = replayed.trace.completed and replayed.discrepancies == observation.discrepancies
                except (OSError, TypeError, ValueError) as error:
                    detail = str(error)
            result = RoundResult(
                *fields, "completed", feedback.reward, len(feedback.novel), feedback.added,
                observation.discrepancies, confirmed, detail,
            )
        if phase == "training":
            self.replay.append(proposal.context, proposal.steps, result.reward)
            sample = self.replay.sample(self.rng)
            self.policy.learn(sample.steps, sample.reward, context=sample.context)
        return result

    def _cycle(self, number, shortlist, training, evaluation, warmup):
        full = tuple(item.name for item in self.planner.catalog)
        results = []
        for _ in range(training):
            results.append(self._round(number, "training", shortlist, 1.0 if warmup else self.settings.epsilon))
        bandit_records = []
        for _ in range(evaluation):
            result = self._round(number, "evaluation", full, 1.0 if warmup else 0.0)
            results.append(result)
            if result.reward is not None:
                bandit_records.append((result.templates, result.templates, result.reward))
        if bandit_records:
            self.bandit.update_cycle(bandit_records, eligible=shortlist)
        return results

    def run(self) -> tuple[RoundResult, ...]:
        if not len(self.corpus):
            raise ValueError("At least one calibrated seed is required")
        rounds = []
        if not self.warmed_up:
            full = tuple(item.name for item in self.planner.catalog)
            rounds.extend(self._cycle(0, full, self.settings.warmup_training, self.settings.warmup_evaluation, True))
            self.warmed_up = True
        for _ in range(self.settings.cycles):
            shortlist = self.bandit.screen(self.planner.catalog, self.rng)
            self.completed_cycles += 1
            rounds.extend(self._cycle(
                self.completed_cycles, shortlist, self.settings.training_rounds, self.settings.evaluation_rounds, False,
            ))
        return tuple(rounds)
