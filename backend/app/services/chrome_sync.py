"""Persisted global Chrome major version and per-module sync switches."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..contracts import ChromeSyncData
from ..crypto import EncryptionContext, parameter_cipher
from ..models import AppSetting, Module
from .ownership import owner_user_id

GLOBAL_KEY = "chrome_major_version"
DEFAULT_CHROME_VERSION = 156
MIN_CHROME_VERSION = 1
MAX_CHROME_VERSION = 999


def _sync_key(module_id: int) -> str:
    return f"chrome_sync:{module_id}"


def valid_chrome_version(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("Chrome 版本必须为整数")
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError("Chrome 版本必须为整数") from exc
    if number < MIN_CHROME_VERSION or number > MAX_CHROME_VERSION:
        raise ValueError(f"Chrome 版本必须在 {MIN_CHROME_VERSION}-{MAX_CHROME_VERSION} 之间")
    return number


async def get_global_chrome_version(db: AsyncSession) -> int:
    row = await db.get(AppSetting, GLOBAL_KEY)
    if row is None:
        return DEFAULT_CHROME_VERSION
    try:
        return valid_chrome_version(row.value)
    except ValueError:
        return DEFAULT_CHROME_VERSION


async def _set_setting(db: AsyncSession, key: str, value: str) -> None:
    row = await db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value


async def module_supports_chrome(module: Module) -> bool:
    return any(
        isinstance(item, dict) and item.get("key") == "chrome_version"
        for item in (module.param_schema or [])
    )


async def module_sync_enabled(db: AsyncSession, module_id: int) -> bool:
    row = await db.get(AppSetting, _sync_key(module_id))
    return bool(row and row.value == "1")


async def _write_module_version(db: AsyncSession, module: Module, version: int) -> bool:
    if not await module_supports_chrome(module):
        return False
    context = EncryptionContext(
        user_id=await owner_user_id(db),
        module_key=module.key,
        account_index=-1,
    )
    params = {}
    if module.params_encrypted:
        try:
            params = parameter_cipher.decrypt(module.params_encrypted, context)
        except Exception:
            return False
    params["chrome_version"] = version
    module.params_encrypted = parameter_cipher.encrypt(params, context)
    return True


async def set_module_sync(
    db: AsyncSession, module: Module, enabled: bool
) -> ChromeSyncData:
    await _set_setting(db, _sync_key(module.id), "1" if enabled else "0")
    if enabled:
        version = await get_global_chrome_version(db)
        await _write_module_version(db, module, version)
    return await get_module_sync(db, module)


async def get_module_sync(db: AsyncSession, module: Module) -> ChromeSyncData:
    context = EncryptionContext(
        user_id=await owner_user_id(db),
        module_key=module.key,
        account_index=-1,
    )
    version: int | None = None
    if module.params_encrypted:
        try:
            raw = parameter_cipher.decrypt(module.params_encrypted, context)
            candidate = raw.get("chrome_version")
            if candidate is not None:
                version = int(candidate)
        except (Exception, ValueError):
            version = None
    return ChromeSyncData(
        supported=await module_supports_chrome(module),
        enabled=await module_sync_enabled(db, module.id),
        chrome_version=version,
    )


async def set_global_chrome_version(db: AsyncSession, value: object) -> tuple[int, int]:
    version = valid_chrome_version(value)
    await _set_setting(db, GLOBAL_KEY, str(version))
    rows = (await db.execute(select(Module))).scalars().all()
    changed = 0
    for module in rows:
        if await module_sync_enabled(db, module.id):
            if await _write_module_version(db, module, version):
                changed += 1
    return version, changed
