from dataclasses import dataclass

from ..benches import Testbench
from ..model import TimingCase, Trace
from .coverage import CoverageExtractor, Feature
from .reference import Discrepancy, ReferenceModel


@dataclass(frozen=True, slots=True)
class Observation:
    trace: Trace
    features: frozenset[Feature]
    discrepancies: tuple[Discrepancy, ...]


class Observer:
    def __init__(self, bench: Testbench, reference: ReferenceModel):
        self.bench = bench
        self.reference = reference
        self.coverage = CoverageExtractor()

    def run(self, case: TimingCase, max_cycles: int) -> Observation:
        trace = self.bench.execute(case, max_cycles=max_cycles)
        previous = -1
        for event in trace.events:
            if not 0 <= event.cycle < max_cycles or event.cycle < previous:
                raise ValueError("Trace events must be ordered and within the cycle budget")
            if event.transaction is not None and not 0 <= event.transaction < len(case.transactions):
                raise ValueError("Trace transaction index is outside the case")
            previous = event.cycle
        features = self.coverage.extract(case, trace)
        return Observation(trace, features, self.reference.check(case, trace))
