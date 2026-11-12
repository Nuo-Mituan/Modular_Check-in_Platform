"""Shared module-parameter validation used by all internal write paths."""

from __future__ import annotations

from typing import Any

from ..models import Module
from ..module_loader import ModuleConfig, validate_and_normalize_params


def config_from_module(module: Module) -> ModuleConfig:
    """Build a validation config from the module's persisted parameter schema."""
    return ModuleConfig(
        name=module.name or module.key,
        params=list(module.param_schema or []),
    )


def validate_module_params(module: Module, params: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize params with the same validator as manual saves."""
    return validate_and_normalize_params(config_from_module(module), params)
