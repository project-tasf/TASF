from dataclasses import replace

from ..model import Control
from .catalog import bind, control_guard, replace_entry


def bound_change(case, template, index, updated, fields):
    old = case.controls[index]
    controls = replace_entry(case.controls, index, updated)
    expected = {name: getattr(updated, name) for name in ("kind", *fields)}
    operands = (index, updated.anchor, updated.offset, updated.duration)
    return bind(template, replace(case, controls=controls), min(old.anchor, updated.anchor),
                operands, control_guard((index, expected)), (index,))


def duration_actions(case, template, profile, prefix):
    if template.name == "create_control":
        if len(case.controls) >= profile.max_controls or profile.max_duration < 1:
            return
        index = len(case.controls)
        for anchor in range(prefix, len(case.transactions)):
            for kind in profile.control_kinds:
                offsets = {0, min(2, profile.max_offset)}
                offsets.update(item.offset + item.duration + 1 for item in case.controls
                               if item.anchor == anchor and item.kind == kind)
                for offset in sorted(offsets):
                    if offset > profile.max_offset:
                        continue
                    for duration in dict.fromkeys((1, min(4, profile.max_duration))):
                        item = Control(kind, anchor, offset, duration)
                        updated = replace(case, controls=case.controls + (item,))
                        yield bind(template, updated, anchor, (kind, anchor, offset, duration),
                                   control_guard((index, {"kind": kind})), (index,))
        return
    for index, item in enumerate(case.controls):
        if item.anchor < prefix:
            continue
        if template.name == "shorten_control":
            lengths = (item.duration - 1, max(1, item.duration // 2))
        else:
            lengths = (item.duration + 1, min(profile.max_duration, 2 * item.duration))
        for length in dict.fromkeys(lengths):
            if length != item.duration and 1 <= length <= profile.max_duration:
                yield bound_change(case, template, index, replace(item, duration=length), ("duration",))


def position_actions(case, template, profile, prefix):
    for index, item in enumerate(case.controls):
        if item.anchor < prefix:
            continue
        if template.name == "change_anchor":
            for anchor in range(prefix, len(case.transactions)):
                if anchor != item.anchor:
                    yield bound_change(case, template, index, replace(item, anchor=anchor), ("anchor",))
        else:
            step = -1 if template.name == "advance_control" else 1
            offset = item.offset + step
            if 0 <= offset <= profile.max_offset:
                yield bound_change(case, template, index, replace(item, offset=offset), ("anchor", "offset"))
