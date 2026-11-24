from collections.abc import Callable, Iterable
from dataclasses import dataclass
from random import Random

from ..benches import Testbench
from ..feedback import Corpus
from ..generation import validate
from ..model import Profile, TimingCase
from ..observation import Discrepancy, Observation, Observer, ReferenceModel
from .planner import case_id
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


class CampaignExecution:
    def __init__(
        self, bench_factory: Callable[[], Testbench], reference_factory: Callable[[], ReferenceModel],
        settings: Settings, profile: Profile, accepts: Callable[[TimingCase], bool] | None,
    ):
        self.bench_factory = bench_factory
        self.reference_factory = reference_factory
        self.settings = settings
        self.profile = profile
        self.accepts = accepts if accepts is not None else lambda case: True
        self.rng = Random(settings.random_seed)
        self.corpus = Corpus()

    def _observe(self, case: TimingCase) -> Observation:
        observer = Observer(self.bench_factory(), self.reference_factory())
        return observer.run(case, self.settings.max_cycles)

    def calibrate(self, seeds: Iterable[TimingCase]) -> None:
        for case in seeds:
            validate(case, self.profile)
            if not self.accepts(case):
                raise ValueError("Calibration case violates the IP constraints")
            self.corpus.admit_seed(case, self._observe(case))

    def _evaluate(
        self, case: TimingCase, cycle: int, phase: str, templates: tuple[str, ...],
    ) -> RoundResult:
        fields = (cycle, phase, case_id(case), templates)
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
        return RoundResult(
            *fields, "completed", feedback.reward, len(feedback.novel), feedback.added,
            observation.discrepancies, confirmed, detail,
        )
