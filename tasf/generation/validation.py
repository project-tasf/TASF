from ..model import Control, Profile, TimingCase, Transaction


def integer(value):
    return type(value) is int


def bounded(value, low, high):
    return integer(value) and low <= value <= high


def validate_profile(profile):
    if not isinstance(profile, Profile):
        raise ValueError("expected a Profile")
    limits = (
        profile.max_transactions, profile.max_wait, profile.max_offset,
        profile.max_duration, profile.max_controls,
    )
    if any(not integer(limit) or limit < 0 for limit in limits):
        raise ValueError("profile limits must be nonnegative integers")
    kinds = profile.control_kinds
    if (not isinstance(kinds, tuple)
            or any(not isinstance(kind, str) or not kind for kind in kinds)
            or len(set(kinds)) != len(kinds)):
        raise ValueError("control kinds must be a tuple of distinct nonempty strings")


def validate(case, profile):
    validate_profile(profile)
    if not isinstance(case, TimingCase):
        raise ValueError("expected a TimingCase")
    if not isinstance(case.transactions, tuple) or not isinstance(case.controls, tuple):
        raise ValueError("transaction and control sequences must be tuples")
    if len(case.transactions) > profile.max_transactions or len(case.controls) > profile.max_controls:
        raise ValueError("case exceeds profile capacity")
    for tx in case.transactions:
        if not isinstance(tx, Transaction) or not integer(tx.value):
            raise ValueError("each transaction must carry an integer")
        if not bounded(tx.wait, 0, profile.max_wait):
            raise ValueError("transaction wait outside profile limits")
    windows = {}
    for item in case.controls:
        if not isinstance(item, Control) or item.kind not in profile.control_kinds:
            raise ValueError("unsupported control")
        if not bounded(item.anchor, 0, len(case.transactions) - 1):
            raise ValueError("control refers to an unavailable transaction")
        if not bounded(item.offset, 0, profile.max_offset):
            raise ValueError("control offset outside profile limits")
        if not bounded(item.duration, 1, profile.max_duration):
            raise ValueError("control duration outside profile limits")
        windows.setdefault((item.kind, item.anchor), []).append(
            (item.offset, item.offset + item.duration)
        )
    for intervals in windows.values():
        intervals.sort()
        if any(right[0] < left[1] for left, right in zip(intervals, intervals[1:])):
            raise ValueError("overlapping windows of the same control at one anchor")
