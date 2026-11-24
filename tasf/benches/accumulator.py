from collections import defaultdict, deque

from ..model import Control, Event, TimingCase, Trace
from .adapters import check_budget


class _ControlSignals:
    def __init__(self, case: TimingCase):
        self.by_anchor: dict[int, list[Control]] = defaultdict(list)
        self.scheduled: dict[int, list[Control]] = defaultdict(list)
        self.active: dict[str, tuple[int, int]] = {}
        for control in case.controls:
            if control.kind not in ("pause", "reset"):
                raise ValueError(f"unsupported accumulator control: {control.kind}")
            if type(control.anchor) is not int or not 0 <= control.anchor < len(case.transactions):
                raise ValueError("control anchor is outside the input sequence")
            if type(control.offset) is not int or control.offset < 0:
                raise ValueError("control offset must be a nonnegative integer")
            if type(control.duration) is not int or control.duration < 1:
                raise ValueError("control duration must be a positive integer")
            self.by_anchor[control.anchor].append(control)

    def on_accept(self, transaction: int, cycle: int) -> None:
        for control in self.by_anchor.get(transaction, ()):
            self.scheduled[cycle + 1 + control.offset].append(control)

    def advance(self, cycle: int, events: list[Event]) -> None:
        for control in self.scheduled.pop(cycle, ()):
            kind = control.kind
            until = cycle + control.duration
            if kind in self.active:
                old_until, anchor = self.active[kind]
                self.active[kind] = max(old_until, until), anchor
            else:
                self.active[kind] = until, control.anchor
                events.append(Event(cycle, f"{kind}_start", control.anchor, 1))
        for kind, (until, anchor) in list(self.active.items()):
            if until == cycle:
                del self.active[kind]
                events.append(Event(cycle, f"{kind}_end", anchor, 0))


class AccumulatorBench:
    def __init__(self, latency: int = 1):
        if type(latency) is not int or latency < 1:
            raise ValueError("latency must be a positive integer")
        self.latency = latency

    def execute(self, case: TimingCase, *, max_cycles: int) -> Trace:
        check_budget(max_cycles)
        for transaction in case.transactions:
            if type(transaction.value) is not int:
                raise ValueError("accumulator inputs must be integers")
            if type(transaction.wait) is not int or transaction.wait < 0:
                raise ValueError("transaction waits must be nonnegative integers")
        signals = _ControlSignals(case)
        if not case.transactions:
            return Trace((), True)
        events: list[Event] = []
        pending: deque[tuple[int, int, int]] = deque()
        total = 0
        enabled_cycle = 0
        index = 0
        next_input = case.transactions[0].wait
        for cycle in range(max_cycles):
            signals.advance(cycle, events)
            if "reset" in signals.active:
                total = 0
                pending.clear()
            elif "pause" not in signals.active:
                if pending and pending[0][0] == enabled_cycle:
                    _, source, value = pending.popleft()
                    events.append(Event(cycle, "output_accepted", source, value))
                if index < len(case.transactions) and cycle >= next_input:
                    value = case.transactions[index].value
                    total += value
                    events.append(Event(cycle, "input_accepted", index, value))
                    pending.append((enabled_cycle + self.latency, index, total))
                    signals.on_accept(index, cycle)
                    index += 1
                    if index < len(case.transactions):
                        next_input = cycle + 1 + case.transactions[index].wait
                enabled_cycle += 1
            if (
                index == len(case.transactions)
                and not pending
                and not signals.scheduled
                and not signals.active
            ):
                return Trace(tuple(events), True)
        return Trace(tuple(events), False)
