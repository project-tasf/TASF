from json import dumps
from random import Random

from tasf.campaign.planner import EditSpace
from tasf.model import TimingCase

from .policy import Decision, EditPolicy, Target


def _band(count: int) -> int:
    return min(4, count.bit_length())


def _summary(case: TimingCase) -> tuple:
    transactions = case.transactions
    controls = case.controls
    recent = tuple(
        ((item.value > 0) - (item.value < 0), _band(item.wait))
        for item in transactions[-2:]
    )
    kinds = tuple(sorted({item.kind for item in controls}))
    return (
        _band(len(transactions)),
        _band(sum(item.wait > 0 for item in transactions)),
        recent,
        _band(len(controls)),
        kinds,
        _band(max((item.duration for item in controls), default=0)),
        _band(max((item.offset for item in controls), default=0)),
        len({item.anchor for item in controls}) < len(controls),
    )


class Neighborhood(EditSpace):
    def propose(
        self, parent: TimingCase, policy: EditPolicy, rng: Random, protected_prefix: int = 0,
    ) -> tuple[TimingCase, tuple[Decision, ...]]:
        path = self.start(parent, protected_prefix)
        families = list(self.families)
        rng.shuffle(families)
        parent_summary = _summary(parent)
        decisions = []
        for family in families:
            by_template = self.candidates(path, self.family_templates(family))
            grouped = {}
            for name, actions in by_template.items():
                for action in actions:
                    target = Target(name, action.target_indices)
                    grouped.setdefault(target, []).append(action)
            if not grouped:
                continue
            retained = sorted(action.template for action in path.retained)
            state = dumps((family, path.prefix, parent_summary, _summary(path.case), retained),
                          separators=(",", ":"))
            options = tuple(grouped)
            choice = policy.choose(state, options, rng)
            if choice not in grouped:
                raise ValueError("policy selected a target outside the legal neighborhood")
            decisions.append(Decision(state, options, choice))
            path.advance(rng.choice(grouped[choice]))
        return path.case, tuple(decisions)
