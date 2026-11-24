from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Transaction:
    value: int
    wait: int = 0


@dataclass(frozen=True, slots=True)
class Control:
    kind: str
    anchor: int
    offset: int
    duration: int


@dataclass(frozen=True, slots=True)
class TimingCase:
    transactions: tuple[Transaction, ...]
    controls: tuple[Control, ...] = ()


@dataclass(frozen=True, slots=True)
class Profile:
    control_kinds: tuple[str, ...] = ("pause", "reset")
    max_transactions: int = 32
    max_wait: int = 32
    max_offset: int = 32
    max_duration: int = 16
    max_controls: int = 16


@dataclass(frozen=True, slots=True)
class Event:
    cycle: int
    kind: str
    transaction: int | None = None
    value: int | None = None


@dataclass(frozen=True, slots=True)
class Trace:
    events: tuple[Event, ...]
    completed: bool
