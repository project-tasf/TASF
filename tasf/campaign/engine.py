from collections.abc import Callable, Iterable

from ..benches import Testbench
from ..feedback import ReplayBuffer
from ..learning import CMAB, GFlowPolicy
from ..model import Profile, TimingCase
from ..observation import ReferenceModel
from .execution import CampaignExecution, RoundResult
from .planner import Planner, case_id
from .settings import Settings


class Campaign(CampaignExecution):
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
        super().__init__(bench_factory, reference_factory, settings, profile, accepts)
        self.bandit = bandit if bandit is not None else CMAB()
        self.policy = policy if policy is not None else GFlowPolicy()
        self.planner = Planner(profile, self.bandit, self.policy, self.accepts, templates)
        self.replay = ReplayBuffer(settings.replay_capacity)
        self.completed_cycles = 0
        self.warmed_up = False

    def _round(self, cycle, phase, scope, epsilon):
        parent = self.corpus.select(self.rng)
        proposal = self.planner.propose(parent, scope, self.rng, epsilon, self.settings.protected_prefix)
        case = proposal.case
        if not proposal.steps:
            result = RoundResult(cycle, phase, case_id(case), proposal.templates, "no_edit", reward=0)
        else:
            result = self._evaluate(case, cycle, phase, proposal.templates)
            if result.reward is None:
                return result
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
