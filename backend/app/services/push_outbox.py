"""Transactional push audit outbox and idempotency-key helpers."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import SessionLocal
from ..models import PushOutbox
from ..timeutils import utcnow
from .redaction import redact_text
from .ring_log import ring_log

logger = logging.getLogger(__name__)
MAX_OUTBOX_ATTEMPTS = 10
DEAD_RETENTION_DAYS = 7
DEAD_MAX_ROWS = 1000
DEAD_CLEANUP_THRESHOLD = 800


def make_idempotency_key(kind: str, *parts: object) -> str:
    digest = hashlib.sha256(
        "\x1f".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()[:32]
    return f"{kind}:{digest}"


def enqueue(
    db: AsyncSession,
    *,
    idempotency_key: str,
    kind: str,
    message: str,
) -> PushOutbox:
    """Add an outbox row; caller must commit it with business state."""
    row = PushOutbox(
        idempotency_key=idempotency_key,
        kind=kind,
        message=redact_text(message),
    )
    db.add(row)
    return row


async def drain(limit: int = 200) -> int:
    """Move pending outbox rows to the ring audit log idempotently."""
    drained = 0
    async with SessionLocal() as db:
        rows = (
            (
                await db.execute(
                    select(PushOutbox)
                    .where(PushOutbox.status == "pending")
                    .order_by(PushOutbox.id.asc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            try:
                seq = await asyncio.to_thread(
                    ring_log.append_push, row.message, "INFO"
                )
                if not seq:
                    raise RuntimeError("环形日志写入未返回 seq")
                row.status = "processed"
                row.processed_at = utcnow()
                row.last_error = None
                drained += 1
            except Exception as exc:  # ring store catches DB errors internally
                row.attempts += 1
                row.last_error = redact_text(f"{type(exc).__name__}: {exc}")
                if row.attempts >= MAX_OUTBOX_ATTEMPTS:
                    row.status = "dead"
                    row.processed_at = utcnow()
                    logger.error(
                        "推送审计 outbox 进入死信：id=%s attempts=%s error=%s",
                        row.id, row.attempts, row.last_error,
                    )
                else:
                    logger.warning("推送审计 outbox 处理失败：%s", row.last_error)
        await db.commit()
    await maybe_cleanup_dead_outbox()
    return drained


async def _dead_count() -> int:
    async with SessionLocal() as db:
        rows = await db.execute(
            select(PushOutbox.id).where(PushOutbox.status == "dead")
        )
        return len(list(rows.scalars()))


async def maybe_cleanup_dead_outbox() -> int:
    """Capacity-triggered cleanup; the periodic purge remains the backstop."""
    if await _dead_count() < DEAD_CLEANUP_THRESHOLD:
        return 0
    return await cleanup_dead_outbox()


async def cleanup_dead_outbox() -> int:
    """Archive and delete expired/excess dead rows; return deleted count."""
    async with SessionLocal() as db:
        rows = (
            (
                await db.execute(
                    select(PushOutbox)
                    .where(PushOutbox.status == "dead")
                    .order_by(PushOutbox.created_at.asc(), PushOutbox.id.asc())
                )
            )
            .scalars()
            .all()
        )
        if not rows:
            return 0
        cutoff = utcnow() - timedelta(days=DEAD_RETENTION_DAYS)
        stale = [row for row in rows if row.created_at < cutoff]
        excess = max(0, len(rows) - len(stale) - DEAD_MAX_ROWS)
        doomed = stale + [row for row in rows if row not in stale][:excess]
        if not doomed:
            return 0
        ids = [row.id for row in doomed]
        await asyncio.to_thread(
            ring_log.append_push,
            f"清理 outbox 死信 count={len(ids)} ids={ids[:20]}",
            "WARNING",
        )
        await db.execute(delete(PushOutbox).where(PushOutbox.id.in_(ids)))
        await db.commit()
        return len(ids)


async def dead_count() -> int:
    return await _dead_count()


async def pending_count() -> int:
    async with SessionLocal() as db:
        rows = await db.execute(
            select(PushOutbox.id).where(PushOutbox.status == "pending")
        )
        return len(list(rows.scalars()))
