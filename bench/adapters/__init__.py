"""Adapter registry. `build(name)` constructs an adapter from env config.

Add a competitor by writing a module with an Adapter-shaped class and
registering its factory here.
"""

from __future__ import annotations

from collections.abc import Callable

from ..core.adapter import Adapter
from .ch import CHAdapter
from .gbrain import GBrainAdapter
from .mock import MockAdapter

_REGISTRY: dict[str, Callable[[], Adapter]] = {
    "mock": MockAdapter,
    "ch": CHAdapter,
    "gbrain": GBrainAdapter,
}


def names() -> list[str]:
    return sorted(_REGISTRY)


def build(name: str) -> Adapter:
    try:
        factory = _REGISTRY[name]
    except KeyError:
        raise SystemExit(f"unknown system '{name}'. available: {', '.join(names())}")
    return factory()
