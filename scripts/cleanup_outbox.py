#!/usr/bin/env python3
"""Manually archive/delete expired or excess dead push-outbox rows."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

backend_path = str(Path(__file__).resolve().parents[1] / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.database import dispose_db, init_db  # noqa: E402
from app.services.push_outbox import cleanup_dead_outbox, dead_count  # noqa: E402


async def _run() -> tuple[int, int]:
    await init_db()
    try:
        deleted = await cleanup_dead_outbox()
        remaining = await dead_count()
        return deleted, remaining
    finally:
        await dispose_db()


def main() -> int:
    deleted, remaining = asyncio.run(_run())
    print(f"dead outbox deleted={deleted} remaining={remaining}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
