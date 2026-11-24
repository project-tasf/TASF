from itertools import pairwise

from ..model import TimingCase, Trace
from .intervals import interval_relation, observed_intervals


Feature = tuple[str, ...]


def distance_band(cycles: int) -> str:
    if cycles <= 1:
        return str(cycles)
    if cycles <= 3:
        return "2-3"
    if cycles <= 7:
        return "4-7"
    return "8+"


def transaction_phase(index: int | None, count: int) -> str:
    if index is None:
        return "unbound"
    if count == 1:
        return "only"
    if index == 0:
        return "first"
    return "last" if index == count - 1 else "middle"


class CoverageExtractor:
    def extract(self, case: TimingCase, trace: Trace) -> frozenset[Feature]:
        count = len(case.transactions)
        phases = {i: transaction_phase(i, count) for i in range(count)}
        features = {
            ("event", event.kind, phases.get(event.transaction, "unbound"))
            for event in trace.events
        }
        transfers = [e for e in trace.events if e.kind in ("input_accepted", "output_accepted")]
        inputs = {e.transaction: e for e in transfers if e.kind == "input_accepted"}
        for output in transfers:
            origin = inputs.get(output.transaction)
            if output.kind == "output_accepted" and origin and output.cycle >= origin.cycle:
                phase = phases.get(output.transaction, "unbound")
                features.add(("latency", phase, distance_band(output.cycle - origin.cycle)))
        for left, right in pairwise(e for e in transfers if e.kind == "input_accepted"):
            features.add(("input_spacing", distance_band(right.cycle - left.cycle)))
        intervals = observed_intervals(trace)
        previous = {}
        for index, interval in enumerate(intervals):
            start, end = interval.start.cycle, interval.end.cycle
            phase = phases.get(interval.start.transaction, "unbound")
            features.add(("duration", interval.kind, phase, distance_band(end - start)))
            prior = previous.get(interval.kind)
            if prior and prior.end.cycle <= start:
                features.add(("release_gap", interval.kind, distance_band(start - prior.end.cycle)))
            previous[interval.kind] = interval
            for kind in ("input_accepted", "output_accepted"):
                before = next((e for e in reversed(transfers) if e.kind == kind and e.cycle <= start), None)
                after = next((e for e in transfers if e.kind == kind and e.cycle >= end), None)
                if before:
                    features.add(("before_control", kind, interval.kind, phase, distance_band(start - before.cycle)))
                if after:
                    features.add(("after_release", interval.kind, kind, phase, distance_band(after.cycle - end)))
            for other in intervals[index + 1:]:
                if interval.start.transaction is not None and interval.start.transaction == other.start.transaction:
                    relation = interval_relation(interval, other)
                    separation = distance_band(other.start.cycle - start)
                    features.add(("control_pair", interval.kind, other.kind, phase, relation, separation))
        return frozenset(features)
