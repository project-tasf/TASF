from collections.abc import Callable
from dataclasses import dataclass, field
from json import dumps

from ..model import TimingCase


@dataclass(frozen=True, slots=True)
class Template:
    name: str
    family: str


_GROUPS = {
    "gap": ("shorten_gap", "lengthen_gap"),
    "duration": ("shorten_control", "lengthen_control", "create_control"),
    "position": ("advance_control", "delay_control", "change_anchor"),
    "relation": (
        "before", "after", "meets", "met_by", "starts_together",
        "ends_together", "overlaps_left", "overlaps_right", "contains", "inside",
    ),
    "suffix": ("duplicate_transaction", "insert_transaction", "delete_transaction"),
    "structure": ("repeat_control", "split_control", "merge_controls"),
}
TEMPLATES = tuple(Template(name, family) for family, names in _GROUPS.items() for name in names)
BY_NAME = {item.name: item for item in TEMPLATES}


@dataclass(frozen=True, slots=True)
class Action:
    template: str
    family: str
    case: TimingCase
    key: str
    protected_prefix: int
    _guard: Callable[[TimingCase], bool] = field(repr=False, compare=False)
    _control_slots: tuple[int, ...] = field(default=(), repr=False)
    _removed_slot: int | None = field(default=None, repr=False)
    _wait_slot: int | None = field(default=None, repr=False)
    _shift_from: int | None = field(default=None, repr=False)

    target_indices: tuple[int | str, ...] = field(default=(), repr=False, compare=False)

    def holds(self, case: TimingCase) -> bool:
        return self._guard(case)

    def preserves(self, earlier: "Action") -> bool:
        if self._removed_slot is not None and any(slot >= self._removed_slot for slot in earlier._control_slots):
            return False
        if self._shift_from is not None and earlier._wait_slot is not None and earlier._wait_slot >= self._shift_from:
            return False
        return earlier.holds(self.case)


def bind(template, case, boundary, operands, guard, slots=(), removed=None, wait_slot=None, shift_from=None):
    key = dumps((template.name, *operands), separators=(",", ":"))
    pair = template.family == "relation" or template.name in ("change_anchor", "create_control", "merge_controls")
    target = tuple(operands[:2]) if pair else (operands[0],)
    return Action(template.name, template.family, case, key, boundary, guard, slots, removed,
                  wait_slot, shift_from, target)


def control_guard(*requirements):
    def holds(case):
        for index, fields in requirements:
            if index >= len(case.controls):
                return False
            control = case.controls[index]
            if any(getattr(control, name) != value for name, value in fields.items()):
                return False
        return True
    return holds


def replace_entry(items, index, value):
    return items[:index] + (value,) + items[index + 1:]
