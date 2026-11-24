from collections import deque
from dataclasses import dataclass
from typing import Protocol

from ..model import TimingCase, Trace


@dataclass(frozen=True, slots=True)
class Discrepancy:
    reason: str
    transaction: int | None
    expected: int | None
    observed: int | None


class ReferenceModel(Protocol):
    def check(self, case: TimingCase, trace: Trace) -> tuple[Discrepancy, ...]: ...


class AccumulatorReference:
    def check(self, case: TimingCase, trace: Trace) -> tuple[Discrepancy, ...]:
        total = 0
        next_input = 0
        pending: deque[tuple[int, int]] = deque()
        discrepancies = []
        for event in trace.events:
            if event.kind == "reset_start":
                total = 0
                pending.clear()
            elif event.kind == "input_accepted":
                if next_input >= len(case.transactions):
                    discrepancies.append(Discrepancy("unexpected_input", event.transaction, None, event.value))
                    continue
                operand = case.transactions[next_input].value
                if (event.transaction, event.value) != (next_input, operand):
                    discrepancies.append(Discrepancy("input_sequence", next_input, operand, event.value))
                total += operand
                pending.append((next_input, total))
                next_input += 1
            elif event.kind == "output_accepted":
                if not pending:
                    discrepancies.append(Discrepancy("unexpected_output", event.transaction, None, event.value))
                    continue
                index, expected = pending.popleft()
                if event.transaction != index:
                    discrepancies.append(Discrepancy("output_order", index, index, event.transaction))
                if event.value != expected:
                    discrepancies.append(Discrepancy("output_value", index, expected, event.value))
        if trace.completed:
            if next_input != len(case.transactions):
                discrepancies.append(Discrepancy("input_count", None, len(case.transactions), next_input))
            for index, expected in pending:
                discrepancies.append(Discrepancy("missing_output", index, expected, None))
        return tuple(discrepancies)
