from collections.abc import Callable, Iterable
from dataclasses import dataclass
from hashlib import sha256
from random import Random

from ..generation import Action, TEMPLATES, actions, validate
from ..learning import CMAB, FlowStep, GFlowPolicy
from ..model import Profile, TimingCase


def case_id(case: TimingCase) -> str:
    return sha256(repr(case).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Proposal:
    case: TimingCase
    context: str
    steps: tuple[FlowStep, ...]
    templates: tuple[str, ...]
    protected_prefix: int


class Planner:
    def __init__(
        self,
        profile: Profile,
        bandit: CMAB,
        policy: GFlowPolicy,
        accepts: Callable[[TimingCase], bool],
        enabled: Iterable[str] | None,
    ):
        self.profile = profile
        self.bandit = bandit
        self.policy = policy
        self.accepts = accepts
        names = {item.name for item in TEMPLATES}
        enabled_names = names if enabled is None else set(enabled)
        if enabled_names - names:
            raise ValueError("Unknown template name")
        families = set()
        if profile.max_transactions:
            families.add("suffix")
            if profile.max_transactions > 1 and profile.max_wait:
                families.add("gap")
            if profile.control_kinds and profile.max_controls and profile.max_duration:
                families.update(("duration", "position", "structure"))
                if profile.max_controls > 1:
                    families.add("relation")
        self.catalog = tuple(
            item for item in TEMPLATES if item.name in enabled_names and item.family in families
        )
        self.families = tuple(dict.fromkeys(item.family for item in self.catalog))

    def _candidates(self, case, templates, prefix, retained, visited):
        by_template = {}
        for template in templates:
            candidates = [
                action for action in actions(case, template.name, self.profile, prefix)
                if action.case not in visited and self.accepts(action.case)
                and all(action.preserves(previous) for previous in retained)
            ]
            if candidates:
                by_template[template.name] = candidates
        return by_template

    def propose(
        self, parent: TimingCase, screened: tuple[str, ...], rng: Random,
        epsilon: float, protected_prefix: int,
    ) -> Proposal:
        validate(parent, self.profile)
        current = parent
        prefix = min(protected_prefix, len(parent.transactions))
        retained: list[Action] = []
        steps = []
        visited = {parent}
        families = list(self.families)
        rng.shuffle(families)
        context = "|".join((case_id(parent), str(prefix), ",".join(families), ",".join(sorted(screened))))
        state = context
        for family in families:
            templates = [item for item in self.catalog if item.family == family]
            shortlist = [item for item in templates if item.name in screened]
            by_template = self._candidates(current, shortlist, prefix, retained, visited)
            if not by_template:
                remaining = [item for item in templates if item.name not in screened]
                available = self._candidates(current, remaining, prefix, retained, visited)
                legal = [item for item in remaining if item.name in available]
                extra = self.bandit.supplement(legal, screened, rng)
                if extra is None:
                    continue
                by_template = {extra: available[extra]}
            options = [action for group in by_template.values() for action in group]
            action, step = self.policy.choose(state + "|" + family, options, rng, epsilon)
            retained.append(action)
            steps.append(step)
            current = action.case
            prefix = max(prefix, action.protected_prefix)
            visited.add(current)
            state += "|" + action.key
        return Proposal(current, context, tuple(steps), tuple(a.template for a in retained), prefix)
