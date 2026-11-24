from collections.abc import Sequence
from random import Random

from ..generation import validate
from ..generation.validation import validate_profile
from ..model import Control, Profile, TimingCase, Transaction

__all__ = ("sample_seeds",)


def sample_seeds(
    profile: Profile,
    rng: Random,
    count: int,
    *,
    operands: Sequence[int] | None = None,
) -> tuple[TimingCase, ...]:
    if type(count) is not int or count < 0:
        raise ValueError("count must be a nonnegative integer")
    if count == 0:
        return ()
    validate_profile(profile)
    if profile.max_transactions < 1:
        raise ValueError("initial seeds require at least one transaction")
    values = range(-4, 5) if operands is None else tuple(operands)
    if not values or any(type(value) is not int for value in values):
        raise ValueError("operands must be a nonempty sequence of integers")
    kinds = profile.control_kinds
    max_length = min(profile.max_transactions, 4)
    max_wait = min(profile.max_wait, 3)
    max_offset = min(profile.max_offset, 2)
    max_duration = min(profile.max_duration, 3)
    max_controls = min(profile.max_controls, 2) if kinds and max_duration else 0
    seeds = []
    for _ in range(count):
        length = rng.randint(1, max_length)
        transactions = tuple(
            Transaction(rng.choice(values), rng.randint(0, max_wait))
            for _ in range(length)
        )
        control_count = rng.randint(0, min(length, max_controls))
        anchors = sorted(rng.sample(range(length), control_count))
        controls = tuple(
            Control(
                rng.choice(kinds),
                anchor,
                rng.randint(0, max_offset),
                rng.randint(1, max_duration),
            )
            for anchor in anchors
        )
        case = TimingCase(transactions, controls)
        validate(case, profile)
        seeds.append(case)
    return tuple(seeds)
