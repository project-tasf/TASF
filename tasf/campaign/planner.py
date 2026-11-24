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


@dataclass(slots=True)
class EditPath:
    case: TimingCase
    prefix: int
    retained: list[Action]
    visited: set[TimingCase]

    def advance(self, action: Action) -> None:
        self.retained.append(action)
        self.case = action.case
        self.prefix = max(self.prefix, action.protected_prefix)
        self.visited.add(action.case)


class EditSpace:
    def __init__(
        self,
        profile: Profile,
        accepts: Callable[[TimingCase], bool],
        enabled: Iterable[str] | None = None,
    ):
        self.profile = profile
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

    def start(self, parent: TimingCase, protected_prefix: int) -> EditPath:
        validate(parent, self.profile)
        return EditPath(parent, min(protected_prefix, len(parent.transactions)), [], {parent})

    def family_templates(self, family: str):
        return [item for item in self.catalog if item.family == family]

    def candidates(self, path: EditPath, templates):
        return self._candidates(path.case, templates, path.prefix, path.retained, path.visited)


class Planner(EditSpace):
    def __init__(
        self,
        profile: Profile,
        bandit: CMAB,
        policy: GFlowPolicy,
        accepts: Callable[[TimingCase], bool],
        enabled: Iterable[str] | None,
    ):
        super().__init__(profile, accepts, enabled)
        self.bandit = bandit
        self.policy = policy

    def propose(
        self, parent: TimingCase, screened: tuple[str, ...], rng: Random,
        epsilon: float, protected_prefix: int,
    ) -> Proposal:
        path = self.start(parent, protected_prefix)
        steps = []
        families = list(self.families)
        rng.shuffle(families)
        context = "|".join((case_id(parent), str(path.prefix), ",".join(families), ",".join(sorted(screened))))
        state = context
        for family in families:
            templates = self.family_templates(family)
            shortlist = [item for item in templates if item.name in screened]
            by_template = self.candidates(path, shortlist)
            if not by_template:
                remaining = [item for item in templates if item.name not in screened]
                available = self.candidates(path, remaining)
                legal = [item for item in remaining if item.name in available]
                extra = self.bandit.supplement(legal, screened, rng)
                if extra is None:
                    continue
                by_template = {extra: available[extra]}
            options = [action for group in by_template.values() for action in group]
            action, step = self.policy.choose(state + "|" + family, options, rng, epsilon)
            path.advance(action)
            steps.append(step)
            state += "|" + action.key
        return Proposal(path.case, context, tuple(steps), tuple(a.template for a in path.retained), path.prefix)
