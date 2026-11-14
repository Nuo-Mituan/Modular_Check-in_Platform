"""Shared module-parameter validation used by all internal write paths."""

from __future__ import annotations

import logging
from typing import Any

from ..models import Module
from ..module_loader import (
    ModuleConfig,
    get_module_physical_path,
    parse_config_file,
    validate_and_normalize_params,
)

logger = logging.getLogger(__name__)


def config_from_module(module: Module) -> ModuleConfig:
    """Prefer the live config.json used by execution; fall back to DB schema."""
    try:
        runtime = parse_config_file(get_module_physical_path(module) / "config.json")
        runtime_schema = [param.model_dump(mode="json") for param in runtime.params]
        if module.param_schema != runtime_schema:
            # Persist the refresh in the caller's transaction so a module file
            # update cannot leave Chrome validation on a stale DB schema.
            module.param_schema = runtime_schema
            logger.info("模块 %s 的 param_schema 已按实时 config.json 刷新", module.key)
        return runtime
    except Exception as exc:
        logger.warning(
            "无法读取模块 %s 的实时 config.json，回退数据库 param_schema: %s",
            module.key, exc,
        )
    return ModuleConfig(
        name=module.name or module.key,
        params=list(module.param_schema or []),
    )


def validate_module_params(module: Module, params: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize params with the same validator as manual saves."""
    return validate_and_normalize_params(config_from_module(module), params)
