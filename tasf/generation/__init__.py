from collections.abc import Iterator

from ..model import Profile, TimingCase
from .catalog import Action, BY_NAME, TEMPLATES, Template
from .controls import duration_actions, position_actions
from .relations import relation_actions
from .structure import structure_actions
from .transactions import gap_actions, suffix_actions
from .validation import bounded, validate

__all__ = ("Action", "Template", "TEMPLATES", "actions", "validate")

_GENERATORS = {
    "gap": gap_actions,
    "duration": duration_actions,
    "position": position_actions,
    "relation": relation_actions,
    "suffix": suffix_actions,
    "structure": structure_actions,
}


def actions(case: TimingCase, template_name: str, profile: Profile,
            protected_prefix: int = 0) -> Iterator[Action]:
    validate(case, profile)
    if not bounded(protected_prefix, 0, len(case.transactions)):
        raise ValueError("protected prefix must be a transaction count within the input sequence")
    if template_name not in BY_NAME:
        raise ValueError(f"unknown edit template: {template_name}")
    template = BY_NAME[template_name]
    for action in _GENERATORS[template.family](case, template, profile, protected_prefix):
        if action.case == case:
            continue
        try:
            validate(action.case, profile)
        except ValueError:
            continue
        yield action
