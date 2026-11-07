#!/usr/bin/env python3
"""Release payload checks for snapshot preflight and upload finalization."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICON_SUFFIXES = (".ico", ".png", ".jpg", ".jpeg", ".webp")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--json", required=True)
    parser.add_argument("--phase", choices=("pre", "full"), default="full")
    args = parser.parse_args()
    release = args.release_dir.resolve()
    checks: list[dict[str, object]] = []

    def check(name: str, ok: bool, msg: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "msg": msg})

    def push(name: str, ok: bool, msg: str) -> None:
        if not ok:
            print(f"FAIL: {msg}", file=sys.stderr)
        check(name, ok, msg)

    push("release_dir", release.is_dir(), f"payload missing: {release}")
    dist = release / "frontend" / "dist"
    dist_files = [p for p in dist.rglob("*") if p.is_file()] if dist.is_dir() else []
    push("frontend_index", (dist / "index.html").is_file(), "frontend dist index.html missing")
    push("frontend_index_nonempty", (dist / "index.html").is_file() and (dist / "index.html").stat().st_size > 0, "frontend dist index.html is empty")
    forbidden_names = (".git", "Releases", ".github", ".env", "backups", "node_modules", ".pnpm-store", "data", "logs", ".venv", ".hypothesis", ".pytest_cache")
    bad_paths = [str(p.relative_to(release)) for p in release.rglob("*") if p.name in forbidden_names]
    push("forbidden_paths", not bad_paths, f"forbidden path: {bad_paths[:3]}")
    bad_files = [str(p.relative_to(release)) for p in release.rglob("*") if p.is_file() and (
        p.name.startswith("test_") or p.name.endswith(".test.mjs") or p.name == "conftest.py"
        or p.suffix in {".zip", ".pyc", ".pem"} or "secret" in p.name.lower()
        or p.name in {"Dockerfile.dev", "pytest.ini"}
    )]
    push("forbidden_files", not bad_files, f"forbidden file: {bad_files[:3]}")
    push("dev_files", not any(p.name in {"Dockerfile.dev", "pytest.ini"} for p in release.rglob("*")), "forbidden dev file")
    push("generator", (Path(__file__).resolve().parent / "release_snapshot.py").is_file(), "release_snapshot.py missing")
    push("backend_main", (release / "backend/app/main.py").is_file(), "backend/app/main.py missing")
    push("modules_excluded", not (release / "modules").exists(), "modules/ must not be in release payload")
    push("down_excluded", not (release / "down").exists(), "down/ must not be in release payload")
    hardcoded = []
    for path in (release / "frontend/src").rglob("*"):
        if path.suffix not in {".vue", ".js", ".ts"} or not path.is_file():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if "1.0." in line and "import.meta.env" not in line and "version" not in line.lower():
                hardcoded.append(f"{path.relative_to(release)}:{lineno}")
    push("version_hardcode", not hardcoded, f"hardcoded frontend version: {hardcoded[:3]}")
    compile_ok = True
    try:
        compile_env = {**os.environ, "PYTHONPYCACHEPREFIX": "/tmp/release-pycache"}
        subprocess.run(
            [sys.executable, "-m", "compileall", "-q", str(release / "backend/app")],
            check=True, capture_output=True, env=compile_env,
        )
    except Exception:
        compile_ok = False
    push("backend_compile", compile_ok, "backend compile failed")

    if args.phase == "full":
        manifest_path = release / "MANIFEST.json"
        sha_path = release / "MANIFEST.sha256"
        push("manifest_exists", manifest_path.is_file(), "MANIFEST.json missing")
        push("manifest_sha_exists", sha_path.is_file(), "MANIFEST.sha256 missing")
        manifest: dict = {}
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                manifest = {}
        sha_text = sha_path.read_text(encoding="utf-8") if sha_path.is_file() else ""
        push("manifest_covered", "  MANIFEST.json" in sha_text, "MANIFEST.json not covered")
        push("manifest_no_self", "  MANIFEST.sha256" not in sha_text, "MANIFEST.sha256 must not hash itself")
        push("dist_included", bool(manifest.get("dist_included")), "manifest does not include dist")
        push("stale_dist_allowed", not manifest.get("stale_dist_allowed"), "stale dist is not allowed")
        push("dist_count", int(manifest.get("dist_file_count", 0)) == len(dist_files), f"dist count {len(dist_files)} != manifest {manifest.get('dist_file_count')}")
        sha_run = subprocess.run(
            ["shasum", "-a", "256", "-c", "MANIFEST.sha256"],
            cwd=release, capture_output=True, text=True,
        )
        ok_count = sha_run.stdout.count(": OK")
        push("checksum", sha_run.returncode == 0 and ok_count == int(manifest.get("expected_sha256_ok", -1)),
             f"OK count {ok_count} != expected")
        generator_hash = manifest.get("generator_sha256")
        actual_hash = hashlib.sha256((Path(__file__).resolve().parent / "release_snapshot.py").read_bytes()).hexdigest()
        push("generator_provenance", bool(generator_hash) and generator_hash == actual_hash, "generator/dist provenance assertion failed")
        if os.environ.get("RELEASE_CHECKLIST_SKIP_NPM") != "1" and (Path.cwd() / "frontend").is_dir():
            npm_ok = subprocess.run(["npm", "ci", "--include=optional"], cwd=Path.cwd() / "frontend", check=False).returncode == 0
            push("npm_ci", npm_ok, "npm ci failed")
        baseline_ok = subprocess.run(
            [sys.executable, "scripts/check_baseline.py", "--baseline", "scripts/release_baseline.json"],
            cwd=ROOT, check=False, capture_output=True,
        ).returncode == 0
        push("baseline", baseline_ok, "baseline gate failed")

    status = "pass" if all(bool(c["ok"]) for c in checks) else "fail"
    payload = {
        "status": status,
        "phase": args.phase,
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
    print(f"checklist={out} phase={args.phase} status={status} checks={len(checks)}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
