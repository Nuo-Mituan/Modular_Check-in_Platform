"""RC6 technical-debt regression tests (Batch 1+)."""

from __future__ import annotations

import time

import pytest

from app.services.lock_registry import KeyLockRegistry


@pytest.mark.asyncio
async def test_td10_lock_registry_is_bounded_and_never_drops_held_lock() -> None:
    registry = KeyLockRegistry[int](max_unlocked=16)
    held = registry.get(999)
    await held.acquire()
    for index in range(100):
        registry.get(index)
    assert registry.size() <= 16
    assert registry.get(999) is held
    assert registry.get(999).locked()
    held.release()
    for index in range(100, 140):
        registry.get(index)
    assert registry.size() <= 16


def test_td05_core_contracts_are_typed() -> None:
    from app.contracts import (
        PushSendResult,
        RingLogEntry,
        SessionPayload,
    )

    assert {"uid", "sid", "iat", "jti"} <= set(SessionPayload.__required_keys__)
    assert {"seq", "level", "text", "created_at"} <= set(
        RingLogEntry.__required_keys__
    )
    assert "sent" in PushSendResult.__optional_keys__


def test_td02_sse_resume_cursor_and_live_frame_dedup() -> None:
    from starlette.requests import Request

    from app.routers.logs import _live_chunk_frame, _resume_cursor
    from app.routers.logs import _ReplayState

    request = Request(
        {
            "type": "http",
            "headers": [(b"last-event-id", b"42")],
            "method": "GET",
            "path": "/api/logs/1/stream",
        }
    )
    assert _resume_cursor(request, 7) == 42
    state = _ReplayState(cursor=42)
    assert _live_chunk_frame({"text": "old", "seq": 42}, state) is None
    frame = _live_chunk_frame({"text": "new", "seq": 43}, state)
    assert frame is not None and "id: 43" in frame and "new" in frame
    assert state.cursor == 43


def test_td03_success_normalization_boundaries() -> None:
    from app.services.execution import (
        ExecutionRejectedError,
        _normalize_result,
    )

    assert _normalize_result({"success": True, "message": "ok"})[:2] == (
        True,
        "ok",
    )
    assert _normalize_result({"success": "false", "msg": "bad"})[:2] == (
        False,
        "bad",
    )
    with pytest.raises(ExecutionRejectedError):
        _normalize_result({"success": "maybe"})
    with pytest.raises(ExecutionRejectedError):
        _normalize_result({"message": "missing"})


def test_td07_idempotency_key_is_stable_and_distinct() -> None:
    from app.services.push_outbox import make_idempotency_key

    first = make_idempotency_key("unified", "2026-10-20")
    assert first == make_idempotency_key("unified", "2026-10-20")
    assert first != make_idempotency_key("unified", "2026-10-21")
    assert first.startswith("unified:")


@pytest.mark.asyncio
async def test_td08_outbox_is_drained_after_commit() -> None:
    from sqlalchemy import select

    from app.database import SessionLocal, init_db
    from app.models import PushOutbox
    from app.services.push_outbox import drain, enqueue, make_idempotency_key

    await init_db()
    key = make_idempotency_key("outbox-test", "cycle")
    async with SessionLocal() as db:
        enqueue(
            db,
            idempotency_key=key,
            kind="unified",
            message="outbox transaction audit",
        )
        await db.commit()
    assert await drain() >= 1
    async with SessionLocal() as db:
        row = await db.scalar(
            select(PushOutbox).where(PushOutbox.idempotency_key == key)
        )
        assert row is not None and row.status == "processed"


def test_td15_push_config_has_bounded_defaults() -> None:
    from app.config import settings

    assert 1 <= settings.push_http_timeout_seconds <= 120
    assert 0.5 <= settings.push_connect_timeout_seconds <= 60
    assert settings.push_request_retry_seconds >= 0
    assert settings.push_response_max_chars >= 200


@pytest.mark.asyncio
async def test_td09_all_skip_batch_terminates_without_api_call() -> None:
    from sqlalchemy import func, select, update

    from app.database import SessionLocal, init_db
    from app.models import Module, PushBatch, PushOutbox, PushPool
    from app.services import push_pool

    await init_db()
    async with SessionLocal() as db:
        from sqlalchemy import delete
        await db.execute(
            update(Module).values(enabled=False, push_unified=False)
        )
        cycle = "2026-11-08"  # Sunday, weekly Monday => all skip
        await db.execute(delete(PushPool).where(PushPool.cycle_id == cycle))
        await db.execute(delete(PushBatch).where(PushBatch.cycle_id == cycle))
        await db.execute(delete(PushOutbox))
        await db.execute(delete(Module).where(Module.key == "td09-all-skip"))
        module = Module(
            key="td09-all-skip",
            name="TD09",
            description="",
            author="",
            default_cron="0 8 * * *",
            cron="0 8 * * *",
            default_start_time="08:00",
            default_end_time="10:00",
            default_repeat_cycle="weekly",
            default_repeat_sub_value="1",
            start_time="08:00",
            end_time="10:00",
            repeat_cycle="weekly",
            repeat_sub_value="1",
            enabled=True,
            push_unified=True,
            push_enabled=True,
            param_schema=[],
        )
        db.add(module)
        await db.commit()
    await push_pool.ensure_batch(cycle)
    assert await push_pool.maybe_flush_batch(cycle) is False
    async with SessionLocal() as db:
        batch = await db.scalar(
            select(PushBatch).where(PushBatch.cycle_id == cycle)
        )
        assert batch is not None
        assert batch.status == "noop"
        assert batch.details_cleared is True
        assert (
            await db.scalar(
                select(func.count())
                .select_from(PushPool)
                .where(PushPool.cycle_id == cycle)
            )
            == 0
        )


@pytest.mark.asyncio
async def test_td11_active_driver_cannot_be_deleted(monkeypatch) -> None:
    from fastapi import HTTPException

    from app.routers import push as push_router

    monkeypatch.setattr(
        push_router.driver_registry,
        "list_drivers",
        lambda: [{"key": "active-driver", "builtin": False}],
    )

    async def fake_config(_db):
        return {"channel": "active-driver", "config": {}}

    monkeypatch.setattr(push_router, "load_push_config", fake_config)
    with pytest.raises(HTTPException) as exc_info:
        await push_router.delete_push_driver("active-driver", db=None)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_td06_concurrent_writer_preserves_seq_order() -> None:
    import threading

    from app.database import init_db
    from app.services.ring_log import ring_log

    await init_db()
    scope = "td06-concurrent"
    errors: list[BaseException] = []

    def worker(worker_id: int) -> None:
        try:
            for index in range(25):
                ring_log.append_execution(
                    module_key=scope,
                    log_id=1,
                    text=f"{worker_id}:{index}\n",
                )
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors
    rows = ring_log.read_scope("module", scope)
    seqs = [row["seq"] for row in rows]
    assert len(seqs) == 100
    assert seqs == sorted(seqs)
    assert all(seqs[i + 1] == seqs[i] + 1 for i in range(len(seqs) - 1))


def test_td13_hub_metrics_and_td16_keepalive() -> None:
    from app.config import settings
    from app.services.hub import ExecutionHub

    hub = ExecutionHub()
    hub.begin(1)
    hub.publish(1, "hello", 1)
    hub.publish(1, "later", 2); hub.record_stream_connection(1, reconnect=True)
    metrics = hub.metrics()
    assert metrics["published_chunks"] == 2
    assert metrics["reconnects"] == 1
    assert "dropped_chunks" in metrics
    assert 5 <= settings.sse_keepalive_seconds <= 120


@pytest.mark.asyncio
async def test_td06_graceful_close_flushes_queue() -> None:
    from app.database import init_db
    from app.services.ring_log import ring_log

    await init_db()
    scope = "td06-close"
    ring_log.append_execution(module_key=scope, log_id=1, text="last-record\n")
    ring_log.close()
    assert ring_log._writer is None, "关闭后写线程必须终止"
    ring_log.initialize()
    rows = ring_log.read_scope("module", scope)
    assert rows and rows[-1]["text"] == "last-record\n"


def test_td14_ring_constants_are_bounded() -> None:
    from app.config import settings

    assert settings.ring_queue_max >= 10
    assert 1 <= settings.ring_write_retries <= 20
    assert settings.ring_trim_max_loops >= 10
    assert 1 <= settings.ring_busy_timeout_seconds <= 120


def test_td20_system_log_route_is_read_only() -> None:
    from app.routers.system import system_router

    route = next(
        route for route in system_router.routes if route.path == "/system/logs"
    )
    assert route.methods == {"GET"}



def test_td12_semver_sort_handles_numeric_segments() -> None:
    from app.push_drivers.registry import version_sort_key

    versions = ["1.2.0", "1.10.0", "1.0.9", "1.0.10"]
    assert sorted(versions, key=version_sort_key) == [
        "1.0.9",
        "1.0.10",
        "1.2.0",
        "1.10.0",
    ]


def test_td17_temp_close_failure_does_not_raise(caplog) -> None:
    from app.services.module_upload import _close_quietly

    class BadHandle:
        def close(self) -> None:
            raise OSError("already closed")

    with caplog.at_level("DEBUG"):
        _close_quietly(BadHandle())
    assert "关闭模块上传临时文件失败" in caplog.text


def test_td19_legacy_output_column_removed() -> None:
    from app.models import ExecutionLog

    assert "output" not in ExecutionLog.__table__.c


def test_td04_update_error_contract() -> None:
    from app.services.module_update import ModuleUpdateError

    error = ModuleUpdateError(400, "周期冲突")
    assert error.status_code == 400
    assert error.detail == "周期冲突"


def test_td04_sensitive_account_merge_preserves_mask() -> None:
    from app.crypto import mask_secret
    from app.routers.modules import _merge_sensitive_accounts

    stored = [{"id": "a1", "label": "", "params": {"cookie": "SECRET-VALUE"}}]
    incoming = [
        {"id": "a1", "label": "", "params": {"cookie": mask_secret("SECRET-VALUE")}}
    ]
    merged = _merge_sensitive_accounts(
        incoming, stored, [{"key": "cookie", "sensitive": True}]
    )
    assert merged[0]["params"]["cookie"] == "SECRET-VALUE"


def test_td18_quality_config_files_exist() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    assert (root / "pyproject.toml").is_file()
    assert (root / "scripts/quality_gate.sh").is_file()
    assert (root / ".github/workflows/quality.yml").is_file()


def test_td18_import_architecture_guard_passes() -> None:
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(root / "scripts/check_imports.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_td19_release_policy_mentions_v2_cleanup() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[2] / "docs/RELEASE_NOTES_v1.0.0-rc.1.md").read_text(
        encoding="utf-8"
    )
    assert "execution_logs.output" in text or "output" in text



@pytest.mark.asyncio
async def test_td08_outbox_stays_pending_when_ring_write_fails(monkeypatch) -> None:
    from sqlalchemy import select

    from app.database import SessionLocal, init_db
    from app.models import PushOutbox
    from app.services import push_outbox

    await init_db()
    key = push_outbox.make_idempotency_key("outbox-fail", str(time.time_ns()))
    async with SessionLocal() as db:
        push_outbox.enqueue(
            db, idempotency_key=key, kind="unified", message="must not be lost"
        )
        await db.commit()
    monkeypatch.setattr(push_outbox.ring_log, "append_push", lambda *_a, **_k: 0)
    await push_outbox.drain()
    async with SessionLocal() as db:
        row = await db.scalar(
            select(PushOutbox).where(PushOutbox.idempotency_key == key)
        )
        assert row is not None
        assert row.status == "pending"
        assert row.attempts >= 1


@pytest.mark.asyncio
async def test_td19a_finalize_does_not_write_output(monkeypatch) -> None:
    from app.models import ExecutionLog
    from app.services.execution import _finalize
    from app.database import SessionLocal, init_db

    await init_db()
    async with SessionLocal() as db:
        row = ExecutionLog(module_id=1, module_key="td19a", module_name="td19a", status="running")
        db.add(row)
        await db.commit()
        log_id = row.id
    from datetime import datetime, timezone

    await _finalize(log_id, 1, "success", "ok", "legacy-output", datetime.now(timezone.utc), 1)
    async with SessionLocal() as db:
        row = await db.get(ExecutionLog, log_id)
        assert row is not None
        assert "日志存储失败" in (row.message or "")




@pytest.mark.asyncio
async def test_td19b_output_backfill_and_column_drop() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.migrations import _migrate_td19_output

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with test_engine.begin() as conn:
        await conn.exec_driver_sql("CREATE TABLE modules (id INTEGER PRIMARY KEY)")
        await conn.exec_driver_sql("INSERT INTO modules (id) VALUES (1)")
        await conn.exec_driver_sql(
            """CREATE TABLE execution_logs (
                id INTEGER PRIMARY KEY, module_id INTEGER NOT NULL,
                module_key TEXT NOT NULL, module_name TEXT NOT NULL,
                trigger_type TEXT NOT NULL, status TEXT NOT NULL,
                message TEXT, output TEXT, started_at TEXT NOT NULL,
                finished_at TEXT, duration_ms INTEGER
            )"""
        )
        await conn.exec_driver_sql("CREATE TABLE ring_logs (seq INTEGER PRIMARY KEY, scope_type TEXT, scope_key TEXT, category TEXT, level TEXT, text TEXT, byte_size INTEGER, created_at TEXT, created_at_epoch INTEGER, ref_type TEXT, ref_id INTEGER)")
        await conn.exec_driver_sql("CREATE TABLE ring_state (id INTEGER PRIMARY KEY, next_seq INTEGER)")
        await conn.exec_driver_sql("INSERT INTO ring_state (id, next_seq) VALUES (1, 1)")
        await conn.exec_driver_sql("INSERT INTO execution_logs (id, module_id, module_key, module_name, trigger_type, status, output, started_at) VALUES (1, 1, 'legacy', 'Legacy', 'manual', 'success', 'old-output', '2026-01-01T00:00:00')")
        await _migrate_td19_output(conn)
        cols = {row[1] for row in (await conn.exec_driver_sql("PRAGMA table_info(execution_logs)")).fetchall()}
        assert "output" not in cols
        result = await conn.exec_driver_sql(
            "SELECT text, ref_id, created_at_epoch FROM ring_logs WHERE ref_type='execution'"
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "old-output" and row[1] == 1
        assert row[2] > 1_700_000_000
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_td19_sqlite_rollback_restores_foreign_keys(monkeypatch) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine
    from app import migrations

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def boom(_connection) -> None:
        raise RuntimeError("forced migration failure")

    monkeypatch.setattr(migrations, "_migrate_td19_output", boom)
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        with pytest.raises(RuntimeError, match="forced"):
            await migrations._run_sqlite_td19(conn)
        enabled = (await conn.exec_driver_sql("PRAGMA foreign_keys")).scalar()
        assert enabled == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_chrome_sync_corrupt_params_raise_conflict() -> None:
    from app.database import SessionLocal, init_db
    from app.models import Module
    from app.services.bootstrap import seed_admin
    from app.services.chrome_sync import ChromeSyncCorruptError, get_module_sync
    from app.config import settings

    await init_db()
    await seed_admin()
    async with SessionLocal() as db:
        module = Module(
            key="chrome-corrupt-test",
            name="Chrome corrupt",
            param_schema=[{"key": "chrome_version", "label": "Chrome", "type": "number"}],
            params_encrypted="not-a-valid-ciphertext",
        )
        db.add(module)
        await db.commit()
        await db.refresh(module)
        with pytest.raises(ChromeSyncCorruptError):
            await get_module_sync(db, module)


@pytest.mark.asyncio
async def test_corrupt_global_chrome_version_marks_degraded() -> None:
    from app.database import SessionLocal, init_db
    from app.models import AppSetting
    from app.services.chrome_sync import GLOBAL_KEY, get_global_chrome_version_with_state

    await init_db()
    async with SessionLocal() as db:
        row = await db.get(AppSetting, GLOBAL_KEY)
        old = row.value if row is not None else None
        if row is None:
            db.add(AppSetting(key=GLOBAL_KEY, value="broken"))
        else:
            row.value = "broken"
        await db.commit()
        version, degraded = await get_global_chrome_version_with_state(db)
        assert version == 156 and degraded is True
        row = await db.get(AppSetting, GLOBAL_KEY)
        if old is None:
            if row is not None:
                await db.delete(row)
        else:
            row.value = old
        await db.commit()
