#!/usr/bin/env python3
"""Safe TD-19 PostgreSQL verification inside a running container.

Creates an isolated `td19_verify_*` schema, never touches public tables.
Run from the application root, e.g.:

    python scripts/verify_td19_postgres.py --rows 10000 --output-bytes 2048

If scripts/ is not present in the container, copy this file first:
    docker cp scripts/verify_td19_postgres.py <container>:/tmp/
    docker exec -it <container> python /tmp/verify_td19_postgres.py
"""
from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import sys
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, ".")
sys.path.insert(0, "backend")
try:
    from app.config import settings
    from app.migrations import _migrate_td19_output
except Exception as exc:  # pragma: no cover - container diagnostics
    print(f"SKIP: cannot import app.config: {exc}")
    raise SystemExit(2)


def _schema_name() -> str:
    return f"td19_verify_{secrets.token_hex(4)}"


async def _scalar(conn, sql: str, params: dict | tuple = ()):
    result = await conn.execute(text(sql), params)
    row = result.fetchone()
    return row[0] if row else None


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=10_000)
    parser.add_argument("--output-bytes", type=int, default=2048)
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    engine = create_async_engine(settings.sqlalchemy_url, pool_pre_ping=True)
    if engine.dialect.name != "postgresql":
        print(f"SKIP: dialect={engine.dialect.name}; PostgreSQL only")
        await engine.dispose()
        return 2

    schema = _schema_name()
    started = time.perf_counter()
    report: dict[str, object] = {"schema": schema, "rows": args.rows}
    try:
        async with engine.begin() as conn:
            await conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            await conn.exec_driver_sql(
                f'''CREATE TABLE "{schema}".modules (id INTEGER PRIMARY KEY)'''
            )
            await conn.exec_driver_sql(
                f'''CREATE TABLE "{schema}".execution_logs (
                    id BIGSERIAL PRIMARY KEY,
                    module_id INTEGER NOT NULL REFERENCES "{schema}".modules(id) ON DELETE CASCADE,
                    module_key VARCHAR(80) NOT NULL,
                    output TEXT
                )'''
            )
            await conn.exec_driver_sql(
                f'''CREATE TABLE "{schema}".ring_logs (
                    seq BIGINT PRIMARY KEY,
                    scope_type VARCHAR(16) NOT NULL,
                    scope_key VARCHAR(160) NOT NULL,
                    category VARCHAR(24) NOT NULL,
                    level VARCHAR(16) NOT NULL,
                    text TEXT NOT NULL,
                    byte_size INTEGER NOT NULL,
                    created_at VARCHAR(40) NOT NULL,
                    created_at_epoch BIGINT NOT NULL,
                    ref_type VARCHAR(24),
                    ref_id BIGINT
                )'''
            )
            await conn.exec_driver_sql(
                f'CREATE TABLE "{schema}".ring_state (id INTEGER PRIMARY KEY, next_seq BIGINT NOT NULL)'
            )
            await conn.exec_driver_sql(f'INSERT INTO "{schema}".ring_state(id, next_seq) VALUES (1, 1)')
            await conn.exec_driver_sql(
                f'INSERT INTO "{schema}".modules(id) VALUES (1)'
            )
            payload = "x" * max(1, args.output_bytes)
            await conn.execute(
                text(f'''INSERT INTO "{schema}".execution_logs(module_id, module_key, output)
                    SELECT 1, 'legacy-module', :payload
                    FROM generate_series(1, :rows)'''),
                {"payload": payload, "rows": args.rows},
            )

        # The setup transaction is committed above; now test a real transaction
        # and roll it back without destroying the isolated schema.
        async with engine.connect() as conn:
            trans = await conn.begin()
            try:
                # 1. Verify SQLAlchemy text binds and the migration's %s path.
                bound = await _scalar(conn, "SELECT :value::int", {"value": 1})
                report["placeholder_binding"] = bound == 1

                # 2. Run the actual application PG migration against the test schema.
                t0 = time.perf_counter()
                await conn.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
                await _migrate_td19_output(conn)
                report["drop_seconds"] = round(time.perf_counter() - t0, 4)
                report["column_absent_in_tx"] = await _scalar(
                    conn,
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_schema=:schema AND table_name='execution_logs' AND column_name='output'",
                    {"schema": schema},
                ) == 0
                lock_modes = (await conn.exec_driver_sql(
                    f'''SELECT DISTINCT mode FROM pg_locks
                        WHERE relation = '"{schema}".execution_logs'::regclass
                        AND pid = pg_backend_pid()'''
                )).scalars().all()
                report["lock_modes"] = lock_modes
                report["backfilled_rows"] = await _scalar(
                    conn, "SELECT count(*) FROM ring_logs WHERE ref_type='execution'"
                )
                report["access_exclusive_lock"] = "AccessExclusiveLock" in lock_modes
            finally:
                await trans.rollback()
        async with engine.connect() as conn:
            report["column_present_after_rollback"] = await _scalar(
                conn,
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_schema=:schema AND table_name='execution_logs' AND column_name='output'",
                {"schema": schema},
            ) == 1
            report["rows_after_rollback"] = await _scalar(
                conn, f'SELECT count(*) FROM "{schema}".execution_logs'
            )
            report["ring_rows_after_rollback"] = await _scalar(
                conn, f'SELECT count(*) FROM "{schema}".ring_logs'
            )
        report["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        report["status"] = "pass" if all(
            bool(report.get(k))
            for k in ("placeholder_binding", "column_absent_in_tx", "access_exclusive_lock",
                      "column_present_after_rollback")
        ) else "fail"
    finally:
        if not args.keep:
            async with engine.begin() as conn:
                await conn.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await engine.dispose()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
