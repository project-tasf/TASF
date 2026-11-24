from dataclasses import replace
from itertools import groupby

from .catalog import bind, control_guard, replace_entry


def shape(item):
    return dict(kind=item.kind, anchor=item.anchor, offset=item.offset, duration=item.duration)


def merge_actions(case, template, profile, prefix):
    eligible = sorted(
        ((i, c) for i, c in enumerate(case.controls) if c.anchor >= prefix),
        key=lambda pair: (pair[1].anchor, pair[1].kind, pair[1].offset),
    )
    for _, group in groupby(eligible, key=lambda pair: (pair[1].anchor, pair[1].kind)):
        neighbors = list(group)
        for (i, left), (j, right) in zip(neighbors, neighbors[1:]):
            span = right.offset + right.duration - left.offset
            if span > profile.max_duration:
                continue
            keep, remove = sorted((i, j))
            combined = replace(left, duration=span)
            controls = replace_entry(case.controls, keep, combined)
            controls = controls[:remove] + controls[remove + 1:]
            yield bind(template, replace(case, controls=controls), left.anchor, (i, j),
                       control_guard((keep, shape(combined))), (keep,), remove)


def structure_actions(case, template, profile, prefix):
    if template.name == "merge_controls":
        yield from merge_actions(case, template, profile, prefix)
        return
    if len(case.controls) >= profile.max_controls:
        return
    for i, item in enumerate(case.controls):
        if item.anchor < prefix:
            continue
        if template.name == "split_control":
            if item.duration < 2:
                continue
            head = replace(item, duration=item.duration // 2)
            tail = replace(item, offset=item.offset + head.duration + 1,
                           duration=item.duration - head.duration)
        else:
            head = item
            tail = replace(item, offset=item.offset + item.duration + 1)
        if tail.offset > profile.max_offset:
            continue
        j = len(case.controls)
        controls = replace_entry(case.controls, i, head) + (tail,)
        yield bind(template, replace(case, controls=controls), item.anchor, (i, tail.offset),
                   control_guard((i, shape(head)), (j, shape(tail))), (i, j))
