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
    new = files - set(bl["mypy_known_error_files"])
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
    bp, cp = base.get("paths", {}), cur.get("paths", {})
    for path, methods in bp.items():
        if path not in cp:
            br.append(f"path_removed:{path}")
            continue
        for method in methods:
            if method not in cp[path]:
                br.append(f"method_removed:{method.upper()} {path}")
    allow = set(bl.get("openapi_breaking_allow", []))
    hard = [x for x in br if x not in allow]
    if hard:
        die(f"OpenAPI breaking: {hard}")
    print(f"ok: OpenAPI breaking=0, paths={len(cp)}")


def check_versions(bl: dict) -> None:
    def txt(p: str) -> str:
        return (ROOT / p).read_text(encoding="utf-8")
    main = re.search(r'^__version__\s*=\s*["\'](.+?)["\']', txt("backend/app/__init__.py"), re.M)
    if not main:
        die("无法读取 __version__")
    v = main.group(1)
    checks = [
        ("pyproject", re.search(r'^version\s*=\s*["\'](.+?)["\']', txt("pyproject.toml"), re.M)),
        ("package", json.loads(txt("frontend/package.json")).get("version")),
        ("package-lock", json.loads(txt("frontend/package-lock.json")).get("version")),
        ("baseline", bl.get("version")),
        ("openapi", load(ROOT / "scripts/openapi_base.json").get("info", {}).get("version")),
    ]
    for f in ("Dockerfile", "Dockerfile.dev"):
        vals = set(re.findall(r'version\s*=\s*["\']?([^"\'\s]+)', txt(f), re.I))
        checks.append((f, vals.pop() if len(vals) == 1 else "missing/ambiguous"))
    for f, label in [("frontend/src/layouts/AppLayout.vue", "AppLayout"), ("frontend/src/views/LoginView.vue", "LoginView")]:
        if "VITE_APP_VERSION" in txt(f):
            checks.append((label, v))
        else:
            m = re.search(r"(['\"])(\d+\.\d+\.\d+)\1", txt(f))
            checks.append((label, m.group(2) if m else "missing"))
    notes = sorted((ROOT / "docs").glob("RELEASE_NOTES_v*.md"))
    checks.append(("notes", notes[-1].stem.split("_v")[-1] if notes else "missing"))
    bad = [(n, x.group(1) if hasattr(x, "group") else x) for n, x in checks if (x.group(1) if hasattr(x, "group") else x) != v]
    if bad:
        die(f"版本不一致（主轴 {v}）: {bad}")
    print(f"ok: 版本交叉校验全部 = {v}")


def check_tech_debt() -> None:
    p = ROOT / "docs" / "TECH_DEBT.md"
    t = p.read_text(encoding="utf-8") if p.is_file() else ""
    nums = {k: int(m.group(1)) for k in ("总数", "已完成", "待清零", "已关闭") if (m := re.search(rf"{k}\D{{0,5}}(\d+)", t))}
    if len(nums) == 4 and nums["总数"] != nums["已完成"] + nums["待清零"] + nums["已关闭"]:
        print(f"WARN: TECH_DEBT 计数不自洽: {nums}")
    else:
        print(f"ok: TECH_DEBT 计数 {nums}")


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
    check_tech_debt()
    print("check_baseline: ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
