from collections.abc import Callable, Mapping

from .accumulator import AccumulatorBench
from .adapters import CallbackBench, JsonBench, Testbench


class BenchRegistry:
    def __init__(self, factories: Mapping[str, Callable[..., Testbench]] | None = None):
        self._factories: dict[str, Callable[..., Testbench]] = {}
        if factories is not None:
            for name, factory in factories.items():
                self.register(name, factory)

    def register(self, name: str, factory: Callable[..., Testbench]) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("a bench name must be a nonempty string")
        if not callable(factory):
            raise TypeError("a bench factory must be callable")
        self._factories[name] = factory

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))

    def create(self, name: str, **options) -> Testbench:
        return self._factories[name](**options)


def default_registry() -> BenchRegistry:
    return BenchRegistry({
        "accumulator": AccumulatorBench,
        "callback": CallbackBench,
        "json": JsonBench,
    })
