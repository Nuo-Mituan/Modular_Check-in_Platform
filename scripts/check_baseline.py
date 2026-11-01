#!/usr/bin/env python3
"""Single release gate for baseline/version/OpenAPI assertions."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def die(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        die(f"无法读取 {path}: {exc}")


def run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def check_pytest(bl: dict) -> None:
    import tempfile
    import xml.etree.ElementTree as ET
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as fh:
        xml_path = fh.name
    try:
        rc, out = run([sys.executable, "-m", "pytest", "-q", "--tb=no", f"--junitxml={xml_path}", "backend/tests"])
        root = ET.parse(xml_path).getroot()
        suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
        tests = sum(int(x.get("tests", 0)) for x in suites)
        failures = sum(int(x.get("failures", 0)) + int(x.get("errors", 0)) for x in suites)
        skipped = sum(int(x.get("skipped", 0)) for x in suites)
        failed = []
        for x in suites:
            for case in x.findall("testcase"):
                if case.find("failure") is not None or case.find("error") is not None:
                    failed.append(f"{case.get('classname','')}::{case.get('name','')}".replace(".", "/", 1))
        passed = tests - failures - skipped
        allowed = {x["id"] for x in bl["pytest_failed_allow"]}
        bad = [f for f in failed if not any(f.endswith(a) or a in f for a in allowed)]
        if passed < bl["pytest_passed_min"] or bad or skipped > bl["pytest_skipped_allow"]:
            die(f"pytest passed={passed} failed={failed} skipped={skipped}; bad={bad}")
        print(f"ok: pytest passed={passed}, failed={len(failed)}, skipped={skipped}")
    finally:
        Path(xml_path).unlink(missing_ok=True)


def check_mypy(bl: dict) -> None:
    rc, out = run([sys.executable, "-m", "mypy", "backend/app"])
    m = re.search(r"Found (\d+) errors? in (\d+) files?", out)
    total = int(m.group(1)) if m else 0
    files = set(re.findall(r"^(backend/app/[^:]+):\d+: error:", out, re.M))
    known = set(bl["mypy_known_error_files"])
    for f in known:
        if not (ROOT / f).is_file():
            print(f"WARN: mypy_known_error_files 路径不存在，可清理: {f}")
    new = files - known
    if total > bl["mypy_total_max"] or new:
        die(f"mypy errors={total}, new_files={sorted(new)}")
    print(f"ok: mypy errors={total} in {len(files)} files; 新增文件错误=0")


def openapi() -> dict:
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
        path = fh.name
    try:
        rc, out = run([sys.executable, "scripts/generate_openapi_snapshot.py", path])
        if rc:
            die("OpenAPI 生成失败")
        return load(Path(path))
    finally:
        Path(path).unlink(missing_ok=True)


def check_openapi(bl: dict, *, regenerate: bool = False) -> None:
    p = ROOT / "scripts" / "openapi_base.json"
    if not p.is_file():
        die("openapi_base.json 不存在")
    base = load(p)
    if regenerate:
        p.write_text(json.dumps(openapi(), sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("REGENERATED: openapi_base.json 已重写 —— 必须单独提交")
        return
    cur = openapi()
    if base.get("info", {}).get("version") != bl["version"]:
        die(f"OpenAPI baseline info.version={base.get('info',{}).get('version')} != {bl['version']}")
    br = []
    nbr = []
    bp, cp = base.get("paths", {}), cur.get("paths", {})
    for path, methods in bp.items():
        if path not in cp:
            br.append(f"path_removed:{path}")
            continue
        for method in methods:
            if method not in cp[path]:
                br.append(f"method_removed:{method.upper()} {path}")
    for path, methods in cp.items():
        if path not in bp:
            nbr.append(f"new_path:{path}")
            continue
        for method in methods:
            if method not in bp[path]:
                nbr.append(f"new_method:{method.upper()} {path}")
    allow = set(bl.get("openapi_breaking_allow", []))
    hard = [x for x in br if x not in allow]
    if hard:
        die(f"OpenAPI breaking: {hard}")
    max_paths = bl.get("openapi_paths_max", len(cp))
    if len(cp) > max_paths:
        die(f"OpenAPI paths={len(cp)} > openapi_paths_max={max_paths}")
    print(f"ok: OpenAPI breaking=0, non-breaking={len(nbr)}, paths={len(cp)}")


def check_versions(bl: dict) -> None:
    """Version equality chain: Python side, npm side, cross-side."""
    def _re(text: str, pat: str):
        m = re.search(pat, text, re.M)
        return m.group(1) if m else None
    items: dict[str, str | None] = {}
    items["backend/app/__init__.py (__version__)"] = _re(
        (ROOT / "backend/app/__init__.py").read_text(encoding="utf-8"),
        r'^__version__\s*=\s*["\']([^"\']+)["\']',
    )
    items["pyproject.toml"] = _re(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        r'^version\s*=\s*["\']([^"\']+)["\']',
    )
    items["frontend/package.json"] = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8")).get("version")
    lockp = ROOT / "frontend/package-lock.json"
    items["frontend/package-lock.json"] = json.loads(lockp.read_text(encoding="utf-8")).get("version") if lockp.is_file() else None
    for f in ("Dockerfile", "Dockerfile.dev"):
        text = (ROOT / f).read_text(encoding="utf-8") if (ROOT / f).is_file() else ""
        vals = set(re.findall(r'version\s*=\s*["\']?([^"\'\s\n]+)', text, re.I))
        items[f"{f} LABEL"] = next(iter(vals)) if len(vals) == 1 else (",".join(sorted(vals)) if vals else None)
    notes = sorted((ROOT / "docs").glob("RELEASE_NOTES_v*.md"))
    items["RELEASE_NOTES 文件名"] = notes[-1].stem.rsplit("_", 1)[-1].replace("v", "") if notes else None
    items["baseline.json"] = str(bl.get("version"))
    bp = ROOT / "scripts/openapi_base.json"
    items["openapi_base info.version"] = json.loads(bp.read_text(encoding="utf-8")).get("info", {}).get("version") if bp.is_file() else None
    groups: dict[str, list[str]] = {}
    for k, v in items.items():
        groups.setdefault(v or "<缺失>", []).append(k)
    if len(groups) == 1:
        print(f"ok: 版本等式链全部 = {next(iter(groups))}")
        return
    for v, ks in sorted(groups.items(), key=lambda x: x[0] or ""):
        print(f"  [{v}] {ks}", file=sys.stderr)
    die("版本等式链断裂（Python 侧与 npm 侧需分别同步后重新断言）")


def check_lockfile(bl: dict) -> None:
    """L2 lockfile consistency gate; read-only."""
    fe = ROOT / "frontend"
    pkg = fe / "package.json"
    lock = fe / "package-lock.json"
    manager = bl.get("lockfile_manager", "npm")
    if not lock.is_file():
        die("package-lock.json 缺失；请先执行 npm ci / npm install 生成 lockfile")
    for name in bl.get("forbidden_lockfiles", []):
        p = fe / name
        if p.is_file() and p.stat().st_size > 0:
            die(f"检测到不受支持的 lockfile: {name}（本项目仅支持 {manager}）")
    try:
        pv = json.loads(pkg.read_text(encoding="utf-8"))["version"]
        lv = json.loads(lock.read_text(encoding="utf-8")).get("version")
    except Exception as exc:
        die(f"读取 package version 失败: {exc}")
    if lv != pv:
        die(f"lockfile version({lv}) != package.json version({pv})；执行 npm install 同步")
    lvv = json.loads(lock.read_text(encoding="utf-8")).get("lockfileVersion")
    if lvv not in (2, 3):
        print(f"WARN: package-lock.json lockfileVersion={lvv} 非预期 2/3（未阻断）")
    print(f"ok: lockfile 一致 (manager={manager}, package={pv}, lock.version={lv})")


def check_tech_debt() -> None:
    p = ROOT / "docs" / "TECH_DEBT.md"
    t = p.read_text(encoding="utf-8") if p.is_file() else ""
    nums = {k: int(m.group(1)) for k in ("总数", "已完成", "待清零", "已关闭") if (m := re.search(rf"{k}\D{{0,5}}(\d+)", t))}
    if len(nums) == 4 and nums["总数"] != nums["已完成"] + nums["待清零"] + nums["已关闭"]:
        print(f"WARN: TECH_DEBT 计数不自洽: {nums}")
    else:
        print(f"ok: TECH_DEBT 计数 {nums}")



def check_release_payload_contract() -> None:
    """TD-23b: validate generated manifest provenance when a payload exists."""
    manifest = Path("Releases") / "v1.0.7" / "MANIFEST.json"
    if not manifest.is_file():
        return
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not data.get("payload_checksum"):
        die("TD-23b: manifest.payload_checksum is missing")
    checklist = data.get("checklist") or {}
    if checklist.get("status") != "pass":
        die("TD-23b: manifest.checklist.status != pass")
    checks = checklist.get("checks") or []
    if len(checks) < 6 or not all(c.get("name") for c in checks):
        die("TD-23b: manifest checklist is incomplete")
    if data.get("git_commit") in (None, "", "unknown"):
        die("TD-23b: manifest.git_commit is missing")
    print(f"ok: release manifest checksum/checklist/git_commit ({data['git_commit']})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default="scripts/release_baseline.json")
    ap.add_argument("--regenerate-baseline", action="store_true")
    args = ap.parse_args()
    bl = load(ROOT / args.baseline)
    if args.regenerate_baseline:
        print(">>> REGENERATED 必须单独提交 <<<")
        check_openapi(bl, regenerate=True)
        return 0
    check_pytest(bl)
    check_mypy(bl)
    check_openapi(bl)
    check_versions(bl)
    check_lockfile(bl)
    check_tech_debt()
    check_release_payload_contract()
    print("check_baseline: ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
