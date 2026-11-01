#!/usr/bin/env python3
"""Create a deterministic non-test release payload from the current working tree.

No git commands are used. The target is Releases/<version>/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git", "Releases", "node_modules", ".venv", "__pycache__",
    ".pnpm-store", ".hypothesis", ".pytest_cache", ".mypy_cache",
    "dist", "tests", "data", "logs", "release", ".ruff_cache", ".github",
    "backups", "tools",
}
EXCLUDED_FILES = {
    ".env", ".DS_Store", "代码审查指令.txt", "对外干净发布指令.txt",
    "MANIFEST.json", "MANIFEST.sha256", "Dockerfile.dev", "pytest.ini",
}
EXCLUDED_SUFFIXES = {".pyc", ".zip", ".log", ".pem", ".key", ".gz", ".tgz"}
TEST_PATTERNS = ("test_*.py", "*_test.py", "*.test.mjs", "conftest.py")


def _is_excluded(rel: Path) -> bool:
    parts = set(rel.parts)
    if parts & EXCLUDED_DIRS:
        return True
    if rel.name in EXCLUDED_FILES:
        return True
    if rel.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    if any(rel.match(pattern) for pattern in TEST_PATTERNS):
        return True
    return False


def _collect(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        rel = path.relative_to(root)
        if _is_excluded(rel):
            continue
        files.append(rel)
    return sorted(files)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--dist-source", type=Path, default=None)
    parser.add_argument("--allow-stale-dist", action="store_true")
    parser.add_argument("--checklist-json", type=Path, default=None)
    args = parser.parse_args()
    root = args.root.resolve()
    target = root / "Releases" / f"v{args.version}"
    if target.parent == target or target == root:
        raise SystemExit("invalid target")

    target.mkdir(parents=True, exist_ok=True)
    notes = target / "RELEASE_NOTES.md"
    saved_notes = notes.read_bytes() if notes.is_file() else b""

    for child in target.iterdir():
        if child == notes:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    files = _collect(root)
    for rel in files:
        destination = target / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / rel, destination)

    dist_files: list[Path] = []
    dist_meta: dict[str, object] = {
        "dist_source": None,
        "dist_generated_at": None,
        "dist_file_count": 0,
    }
    if args.dist_source is not None:
        dist_source = args.dist_source.resolve()
        target_resolved = target.resolve()
        if dist_source == target_resolved or target_resolved in dist_source.parents or "Releases" in dist_source.parts:
            raise SystemExit("dist source must not live under Releases/")
        if not dist_source.is_dir() or not any(dist_source.iterdir()):
            raise SystemExit("dist source is missing or empty")
        if not (dist_source / "index.html").is_file():
            raise SystemExit("dist source must contain index.html")
        dist_newest = max(p.stat().st_mtime for p in dist_source.rglob("*") if p.is_file())
        source_newest = max(
            p.stat().st_mtime for p in root.rglob("*")
            if p.is_file()
            and ".git" not in p.parts
            and "Releases" not in p.parts
            and not _is_excluded(p.relative_to(root))
        )
        if dist_newest < source_newest and not args.allow_stale_dist:
            raise SystemExit("stale dist: dist mtime older than source tree")
        empty = [p for p in dist_source.rglob("*") if p.is_file() and p.stat().st_size == 0]
        if empty:
            raise SystemExit(f"dist contains empty files: {empty[:3]}")
        for source in sorted(dist_source.rglob("*")):
            if not source.is_file():
                continue
            rel = source.relative_to(dist_source)
            destination = target / "frontend" / "dist" / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            dist_files.append(Path("frontend/dist") / rel)
        dist_meta = {
            "dist_source": str(dist_source),
            "dist_generated_at": datetime.fromtimestamp(dist_newest, timezone.utc).isoformat(),
            "dist_file_count": len(dist_files),
            "dist_build_command": os.environ.get("DIST_BUILD_COMMAND"),
            "node_version": os.environ.get("NODE_VERSION"),
        }

    checklist = None
    if args.checklist_json is not None:
        import subprocess
        checklist_path = args.checklist_json.resolve()
        result = subprocess.run([
            os.sys.executable, str(ROOT / "scripts" / "release_checklist.py"),
            "--release-dir", str(target), "--json", str(checklist_path),
        ], check=False)
        if result.returncode != 0:
            for name in ("MANIFEST.json", "MANIFEST.sha256"):
                path = target / name
                if path.exists():
                    path.unlink()
            print("checklist gate failed; manifest not written", file=os.sys.stderr)
            return 1
        checklist = json.loads(checklist_path.read_text(encoding="utf-8"))

    if saved_notes:
        notes.write_bytes(saved_notes)
    elif not notes.exists():
        notes.write_text("# Release notes\n", encoding="utf-8")

    included = sorted(set(files) | set(dist_files) | {Path("RELEASE_NOTES.md")})
    generated_at = os.environ.get(
        "RELEASE_TIMESTAMP",
        datetime.now(timezone.utc).isoformat(),
    )
    manifest = {
        "version": args.version,
        "generated_at": generated_at,
        "bytes_scope": "copied_file_count+dist_file_count (notes and manifests excluded)",
        "generator_sha256": _sha256(Path(__file__)),
        "source_root": ".",
        "file_count": len(files) + len(dist_files),
        "copied_file_count": len(files),
        "dist_file_count": len(dist_files),
        "dist_included": bool(dist_files),
        "git_commit": os.environ.get("GIT_COMMIT", "unknown"),
        "payload_checksum": None,
        "checklist": checklist,
        "stale_dist_allowed": bool(args.allow_stale_dist),
        **dist_meta,
        "release_notes": "RELEASE_NOTES.md",
        "payload_file_count": len(files) + len(dist_files) + 1 + 2,
        "payload_bytes": sum((target / rel).stat().st_size for rel in (files + dist_files)),
        "expected_sha256_ok": len(files) + len(dist_files) + 1 + 2 - 1,
        "files": {str(rel): _sha256(target / rel) for rel in included},
        "excluded": {
            "directories": sorted(EXCLUDED_DIRS),
            "files": sorted(EXCLUDED_FILES),
            "suffixes": sorted(EXCLUDED_SUFFIXES),
            "test_patterns": list(TEST_PATTERNS),
        },
    }
    manifest["payload_checksum"] = hashlib.sha256(
        "".join(f"{manifest['files'][str(rel)]}{rel}" for rel in included).encode()
    ).hexdigest()
    (target / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_path = target / "MANIFEST.json"
    lines = [f"{manifest['files'][str(rel)]}  {rel}" for rel in included]
    lines.append(f"{_sha256(manifest_path)}  MANIFEST.json")
    (target / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")

    forbidden = [
        p for p in target.rglob("*")
        if p.is_file()
        and p.name not in {"MANIFEST.json", "MANIFEST.sha256", "checklist.json"}
        and not (
            args.dist_source is not None
            and p.relative_to(target).parts[:2] == ("frontend", "dist")
        )
        and (
            _is_excluded(p.relative_to(target))
            or ".git" in p.parts
            or "tests" in p.parts
            or "backups" in p.parts
            or ".github" in p.parts
            or p.name in {"Dockerfile.dev", "pytest.ini"}
            or p.suffix.lower() in {".zip", ".pyc", ".gz", ".tgz"}
            or p.name == ".env"
        )
    ]
    if forbidden:
        raise SystemExit(f"forbidden payload files: {forbidden[:5]}")
    if args.dist_source is not None and not (target / "frontend/dist/index.html").is_file():
        raise SystemExit("dist injection failed")
    print(f"payload={target}")
    print(f"files={len(included)} bytes={sum((target/rel).stat().st_size for rel in included)}")
    print(f"manifest={target / 'MANIFEST.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
