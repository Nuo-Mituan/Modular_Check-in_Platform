#!/usr/bin/env python3
"""Machine-readable release payload checks used as a snapshot gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--json", required=True)
    args = parser.parse_args()
    release = args.release_dir.resolve()
    checks: list[dict[str, object]] = []

    def check(name: str, ok: bool, msg: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "msg": msg})

    check("release_dir", release.is_dir(), str(release))
    dist = release / "frontend/dist"
    dist_files = [p for p in dist.rglob("*") if p.is_file()] if dist.is_dir() else []
    check("frontend_index", (dist / "index.html").is_file())
    check("dist_included", bool(dist_files), "copied frontend dist")
    check("dist_count", len(dist_files) > 0, "copied dist file count")
    check("version", os.environ.get("APP_VERSION", "1.0.7") == "1.0.7")
    check("generator", (Path(__file__).resolve().parent / "release_snapshot.py").is_file())
    status = "pass" if all(bool(c["ok"]) for c in checks) else "fail"
    payload = {
        "status": status,
        "checks": checks,
        "provenance": {
            "git_commit": os.environ.get("GIT_COMMIT", "unknown"),
            "built_at": datetime.now(timezone.utc).isoformat(),
            "generator": "release_checklist.py",
        },
    }
    out = Path(args.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, out)
    print(f"checklist={out} status={status}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
