from collections.abc import Callable, Sequence
from random import Random

from tasf.generation import validate
from tasf.generation.validation import validate_profile
from tasf.model import Control, Profile, TimingCase, Transaction
from tasf.seeding import operand_domain


class RandomTesting:
    def __init__(self, operands: Sequence[int] | None = None, max_attempts: int = 32):
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        self.operands = operand_domain(operands)
        self.max_attempts = max_attempts

    def _sample(self, profile: Profile, rng: Random) -> TimingCase:
        if not profile.max_transactions:
            return TimingCase(())
        length = rng.randint(1, profile.max_transactions)
        transactions = tuple(
            Transaction(rng.choice(self.operands), rng.randint(0, profile.max_wait))
            for _ in range(length)
        )
        controls = []
        if profile.control_kinds and profile.max_duration:
            for _ in range(rng.randint(0, profile.max_controls)):
                control = Control(
                    rng.choice(profile.control_kinds), rng.randrange(length),
                    rng.randint(0, profile.max_offset), rng.randint(1, profile.max_duration),
                )
                controls.append(control)
        return TimingCase(transactions, tuple(controls))

    def propose(
        self, profile: Profile, accepts: Callable[[TimingCase], bool], rng: Random,
    ) -> TimingCase | None:
        validate_profile(profile)
        for _ in range(self.max_attempts):
            case = self._sample(profile, rng)
            try:
                validate(case, profile)
            except ValueError:
                continue
            if accepts(case):
                return case
        return None
