"""Bootstrap tasks executed once at application startup."""

from __future__ import annotations

import asyncio
import logging
import secrets
import sys

from sqlalchemy import func, select

from ..config import settings
from ..database import SessionLocal
from ..models import Module, User
from ..module_loader import SyncResult, sync_modules
from ..security import hash_password, verify_password

logger = logging.getLogger(__name__)


async def seed_admin() -> bool:
    async with SessionLocal() as db:
        user_count = await db.scalar(select(func.count()).select_from(User))
        if user_count and user_count > 0:
            admin = await db.scalar(
                select(User).where(User.username == (settings.admin_user or "admin"))
            )
            if (
                admin is not None
                and not admin.password_must_change
                and await asyncio.to_thread(
                    verify_password, "admin123", admin.password_hash or ""
                )
            ):
                admin.password_must_change = True
                await db.commit()
                logger.warning("检测到管理员仍使用默认弱口令，已要求下次登录改密")
            return False

        username = (settings.admin_user or "admin").strip()[:64] or "admin"
        configured = settings.admin_pass.strip()
        if configured and configured != "admin123":
            password = configured
            must_change = False
        else:
            password = secrets.token_urlsafe(12)
            must_change = True
            if sys.__stdout__ is not None:
                sys.__stdout__.write(f"\n🔑 [INIT] Generated admin password: {password}\n")
                sys.__stdout__.flush()
        db.add(
            User(
                username=username,
                password_hash=await asyncio.to_thread(hash_password, password),
                password_must_change=must_change,
            )
        )
        await db.commit()
        logger.warning("首次部署：已创建管理员账号 %s。首次登录必须修改密码。", username)
        return True


async def load_all_modules() -> list[Module]:
    async with SessionLocal() as db:
        return list((await db.execute(select(Module))).scalars().all())


async def initialize_modules() -> SyncResult:
    async with SessionLocal() as db:
        return await sync_modules(db)
