from dataclasses import replace
from itertools import combinations

from .catalog import bind, replace_entry


def delta_range(name, a, b, limit):
    intervals = {
        "before": (-limit, -a - 1),
        "after": (b + 1, limit),
        "meets": (-a, -a),
        "met_by": (b, b),
        "starts_together": (0, 0),
        "ends_together": (b - a, b - a),
        "overlaps_left": (1 - a, min(-1, b - a - 1)),
        "overlaps_right": (max(1, b - a + 1), b - 1),
        "contains": (b - a + 1, -1),
        "inside": (1, b - a - 1),
    }
    low, high = intervals[name]
    return max(-limit, low), min(limit, high)


def relation_guard(name, i, j, kinds):
    def holds(case):
        if j >= len(case.controls):
            return False
        first, second = case.controls[i], case.controls[j]
        if (first.kind, second.kind) != kinds or first.anchor != second.anchor:
            return False
        delta = first.offset - second.offset
        low, high = delta_range(name, first.duration, second.duration, abs(delta))
        return low <= delta <= high
    return holds


def relation_actions(case, template, profile, prefix):
    available = [(i, c) for i, c in enumerate(case.controls) if c.anchor >= prefix]
    for (i, a), (j, b) in combinations(available, 2):
        if a.anchor != b.anchor:
            continue
        low, high = delta_range(template.name, a.duration, b.duration, profile.max_offset)
        previous = a.offset - b.offset
        if low > high or low <= previous <= high:
            continue
        delta = min(max(low, previous), high)
        b_offset = min(max(b.offset, -delta), profile.max_offset - max(delta, 0))
        controls = replace_entry(case.controls, i, replace(a, offset=b_offset + delta))
        controls = replace_entry(controls, j, replace(b, offset=b_offset))
        yield bind(template, replace(case, controls=controls), a.anchor, (i, j, delta, b_offset),
                   relation_guard(template.name, i, j, (a.kind, b.kind)), (i, j))
