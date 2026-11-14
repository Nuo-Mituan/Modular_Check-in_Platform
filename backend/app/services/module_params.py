"""Shared module-parameter validation used by all internal write paths."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from ..models import Module
from ..module_loader import (
    ModuleConfig,
    get_module_physical_path,
    parse_config_file,
    validate_and_normalize_params,
)

logger = logging.getLogger(__name__)


class ModuleConfigReadError(RuntimeError):
    """config.json exists but cannot be read or parsed."""


def _cached_config(module: Module) -> ModuleConfig:
    return ModuleConfig(
        name=module.name or module.key,
        params=list(module.param_schema or []),
    )


def _read_runtime_config(path: Path) -> ModuleConfig | None:
    """Worker-thread helper: stat, read and parse without blocking the loop."""
    if not path.is_file():
        return None
    return parse_config_file(path)


async def load_module_config(module: Module, *, persist_schema: bool = True) -> ModuleConfig:
    """Load the live config.json; a missing file falls back to the DB schema.

    A present but broken config.json is not silently replaced by stale data:
    callers must surface it so the user can repair the module.
    """
    path = get_module_physical_path(module) / "config.json"
    try:
        runtime = await asyncio.to_thread(_read_runtime_config, path)
    except Exception as exc:
        logger.error("模块 %s 的 config.json 解析失败: %s", module.key, exc)
        raise ModuleConfigReadError(
            f"模块 {module.key} 的 config.json 无法解析，请修复模块配置"
        ) from exc
    if runtime is None:
        logger.info("模块 %s 缺少 config.json，使用数据库 param_schema", module.key)
        return _cached_config(module)
    runtime_schema = [param.model_dump(mode="json") for param in runtime.params]
    if persist_schema and module.param_schema != runtime_schema:
        # Only write paths may mark the ORM object dirty; GET must stay read-only.
        module.param_schema = runtime_schema
        logger.info("模块 %s 的 param_schema 已按实时 config.json 刷新", module.key)
    return runtime


def config_from_module(module: Module) -> ModuleConfig:
    """Synchronous compatibility helper, primarily for unit tests.

    Runtime request paths must use load_module_config() so file IO runs in a
    worker thread and broken files can be surfaced explicitly.
    """
    path = get_module_physical_path(module) / "config.json"
    if not path.is_file():
        return _cached_config(module)
    runtime = parse_config_file(path)
    runtime_schema = [param.model_dump(mode="json") for param in runtime.params]
    if module.param_schema != runtime_schema:
        module.param_schema = runtime_schema
    return runtime


def validate_module_params(module: Module, params: dict[str, Any]) -> dict[str, Any]:
    """Validate params against the current module schema."""
    return validate_and_normalize_params(config_from_module(module), params)


def validate_module_params_with_config(
    config: ModuleConfig, params: dict[str, Any]
) -> dict[str, Any]:
    """Validate against an already loaded config; avoids duplicate file IO."""
    return validate_and_normalize_params(config, params)


async def validate_module_params_async(
    module: Module, params: dict[str, Any]
) -> dict[str, Any]:
    """Async validation path; file IO runs outside the event loop."""
    config = await load_module_config(module)
    return validate_and_normalize_params(config, params)
