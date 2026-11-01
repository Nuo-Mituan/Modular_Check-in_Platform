"""Metric provider registry used to avoid service -> app.main imports."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

MetricProvider = Callable[[], Mapping[str, Any]]

_providers: dict[str, MetricProvider] = {}


def register_provider(name: str, provider: MetricProvider) -> None:
    """Register or replace a named metric provider."""
    if not name:
        raise ValueError("metric provider name must not be empty")
    _providers[name] = provider


def merge_providers() -> dict[str, Any]:
    """Merge all providers, rejecting silent key collisions."""
    merged: dict[str, Any] = {}
    owners: dict[str, str] = {}
    for name, provider in _providers.items():
        for key, value in provider().items():
            if key in merged and merged[key] != value:
                raise ValueError(
                    f"metric key collision: {key} from {owners[key]} and {name}"
                )
            merged[key] = value
            owners[key] = name
    return merged
