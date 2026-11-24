from dataclasses import dataclass

from ..model import Event, Trace


@dataclass(frozen=True, slots=True)
class Interval:
    kind: str
    start: Event
    end: Event


def observed_intervals(trace: Trace) -> tuple[Interval, ...]:
    active: dict[str, Event] = {}
    intervals = []
    for event in trace.events:
        kind, separator, edge = event.kind.rpartition("_")
        if not separator:
            continue
        if edge == "start":
            active[kind] = event
        elif edge == "end" and kind in active:
            intervals.append(Interval(kind, active.pop(kind), event))
    return tuple(sorted(intervals, key=lambda item: item.start.cycle))


def interval_relation(left: Interval, right: Interval) -> str:
    a, b = left.start.cycle, left.end.cycle
    c, d = right.start.cycle, right.end.cycle
    if a == c:
        return "same_start"
    if b == d:
        return "same_end"
    if b < c:
        return "before"
    if d < a:
        return "after"
    if b == c:
        return "meets"
    if d == a:
        return "met_by"
    if a <= c and d <= b:
        return "contains"
    if c <= a and b <= d:
        return "within"
    return "overlaps" if a < c else "overlapped_by"
