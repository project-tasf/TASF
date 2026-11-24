from collections.abc import Callable
from dataclasses import asdict
from typing import Protocol

from ..model import Event, TimingCase, Trace


class Testbench(Protocol):
    def execute(self, case: TimingCase, *, max_cycles: int) -> Trace: ...


class BenchCallback(Protocol):
    def __call__(self, case: TimingCase, *, max_cycles: int) -> Trace: ...


def check_budget(max_cycles: int) -> None:
    if type(max_cycles) is not int or max_cycles < 0:
        raise ValueError("max_cycles must be a nonnegative integer")


class CallbackBench:
    def __init__(self, callback: BenchCallback):
        self.callback = callback

    def execute(self, case: TimingCase, *, max_cycles: int) -> Trace:
        check_budget(max_cycles)
        trace = self.callback(case, max_cycles=max_cycles)
        if not isinstance(trace, Trace):
            raise TypeError("the callback must return a Trace")
        return trace


class JsonBench:
    def __init__(self, exchange: Callable[[dict], dict]):
        self.exchange = exchange

    def execute(self, case: TimingCase, *, max_cycles: int) -> Trace:
        check_budget(max_cycles)
        request = {
            "case": {
                "transactions": [asdict(item) for item in case.transactions],
                "controls": [asdict(item) for item in case.controls],
            },
            "max_cycles": max_cycles,
        }
        result = self.exchange(request)
        if not isinstance(result, dict) or type(result.get("completed")) is not bool:
            raise ValueError("the response must contain a boolean completed flag")
        if not isinstance(result.get("events"), list):
            raise ValueError("the response must contain an events array")
        events = []
        previous_cycle = -1
        for item in result["events"]:
            if not isinstance(item, dict):
                raise ValueError("each event must be an object")
            cycle = item.get("cycle")
            kind = item.get("kind")
            transaction = item.get("transaction")
            value = item.get("value")
            if type(cycle) is not int or not 0 <= cycle < max_cycles:
                raise ValueError("event cycle exceeds the execution window")
            if cycle < previous_cycle:
                raise ValueError("events must be in chronological order")
            if not isinstance(kind, str) or not kind:
                raise ValueError("event kind must be a nonempty string")
            if transaction is not None and (
                type(transaction) is not int or not 0 <= transaction < len(case.transactions)
            ):
                raise ValueError("event transaction must be a valid index or null")
            if value is not None and type(value) is not int:
                raise ValueError("event value must be an integer or null")
            events.append(Event(cycle, kind, transaction, value))
            previous_cycle = cycle
        return Trace(tuple(events), result["completed"])
