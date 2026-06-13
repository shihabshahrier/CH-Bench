"""Suite registry. `build(name)` constructs a suite (lazily loading its data)."""

from __future__ import annotations

from collections.abc import Callable

from ..core.suite import Suite
from .contextheavy import ContextHeavySuite
from .locomo import LoCoMoSuite
from .longmemeval import LongMemEvalSuite

_REGISTRY: dict[str, Callable[[], Suite]] = {
    "contextheavy": ContextHeavySuite,
    "longmemeval": LongMemEvalSuite,
    "locomo": LoCoMoSuite,
}


def names() -> list[str]:
    return sorted(_REGISTRY)


def build(name: str) -> Suite:
    try:
        factory = _REGISTRY[name]
    except KeyError:
        raise SystemExit(f"unknown suite '{name}'. available: {', '.join(names())}")
    return factory()
