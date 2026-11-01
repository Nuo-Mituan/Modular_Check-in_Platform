#!/usr/bin/env bash
set -euo pipefail
VERSION="${1:-1.0.7}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAYLOAD="$ROOT/Releases/v${VERSION}"
fail() { echo "FAIL: $*" >&2; exit 1; }
step() { echo "== $* =="; }

[ -d "$PAYLOAD" ] || fail "payload missing: $PAYLOAD"
[ -f "$PAYLOAD/frontend/dist/index.html" ] || fail "frontend dist missing; build and inject with --dist-source first"
[ -s "$PAYLOAD/frontend/dist/index.html" ] || fail "frontend dist index.html is empty"
for forbidden in .git Releases .github .env backups node_modules .pnpm-store data logs .venv .hypothesis .pytest_cache; do
  find "$PAYLOAD" -name "$forbidden" -print -quit | grep -q . && fail "forbidden path: $forbidden"
done
find "$PAYLOAD" \( -name 'test_*.py' -o -name '*.test.mjs' -o -name conftest.py -o -type d -name tests -o -name '*.zip' -o -name '*.tar.gz' -o -name '__pycache__' -o -name '*.pyc' -o -name '*.pem' -o -name '*secret*' \) -print -quit | grep -q . && fail "forbidden test/cache/archive/secret file"
[ -f "$PAYLOAD/MANIFEST.json" ] || fail "MANIFEST.json missing"
[ -f "$PAYLOAD/MANIFEST.sha256" ] || fail "MANIFEST.sha256 missing"
grep -q '  MANIFEST.json$' "$PAYLOAD/MANIFEST.sha256" || fail "MANIFEST.json not covered by MANIFEST.sha256"
grep -q '  MANIFEST.sha256$' "$PAYLOAD/MANIFEST.sha256" && fail "MANIFEST.sha256 must not hash itself" || true
for forbidden in Dockerfile.dev pytest.ini; do
  find "$PAYLOAD" -name "$forbidden" -print -quit | grep -q . && fail "forbidden dev file: $forbidden"
done
cd "$PAYLOAD"
python3 -c "import hashlib,json,pathlib,sys;m=json.load(open('MANIFEST.json'));g=m.get('generator_sha256');sys.exit('generator missing') if not g else None;a=hashlib.sha256(pathlib.Path('scripts/release_snapshot.py').read_bytes()).hexdigest();sys.exit('generator mismatch') if a!=g else None;sys.exit('dist provenance missing') if m.get('dist_included') and (not m.get('dist_source') or not m.get('dist_generated_at')) else None"
shasum -a 256 -c MANIFEST.sha256 > /tmp/release-sha-check.log 2>&1 || { cat /tmp/release-sha-check.log; fail "manifest checksum failed"; }
OK_COUNT=$(grep -c ': OK$' /tmp/release-sha-check.log || true)
FAIL_COUNT=$(grep -vc ': OK$' /tmp/release-sha-check.log || true)
[ "$FAIL_COUNT" -eq 0 ] || fail "checksum failures: $FAIL_COUNT"
EXPECTED=$(python3 - <<'PY'
import json
print(json.load(open('MANIFEST.json'))['expected_sha256_ok'])
PY
)
[ "$OK_COUNT" -eq "$EXPECTED" ] || fail "OK count $OK_COUNT != expected_sha256_ok $EXPECTED"
python3 - <<'PY'
import json, pathlib, sys
m=json.load(open('MANIFEST.json'))
if not m.get('dist_included') or m.get('dist_file_count', 0) <= 0:
    sys.exit('manifest does not include dist')
if m.get('stale_dist_allowed'):
    sys.exit('stale dist is not allowed for v1.0.6')
actual=sum(1 for p in pathlib.Path('frontend/dist').rglob('*') if p.is_file())
if actual != m.get('dist_file_count'):
    sys.exit(f'dist count {actual} != manifest {m.get("dist_file_count")}')
PY
PYTHONPYCACHEPREFIX=/tmp/release-pycache python3 -m compileall -q backend/app || fail "backend compile failed"
[ -f backend/app/main.py ] || fail "backend/app/main.py missing"
for m in demo_checkin e-hentai ikuuu_vpn moyu_energy trae; do
  [ -d "modules/$m" ] || fail "module missing: $m"
done
python3 - <<'PY'
import json, pathlib, sys
p=pathlib.Path('modules/demo_checkin/config.json')
data=json.loads(p.read_text())
icon=str(data.get('icon',''))
if not icon.lower().endswith(('.ico','.png','.jpg','.jpeg','.webp')):
    sys.exit(f'unsupported icon: {icon}')
print('smoke: ok')
PY
echo "OK: $OK_COUNT files (expected_sha256_ok=$EXPECTED)"
shasum -a 256 MANIFEST.sha256
step "syntax/version lint"
if grep -rnE "(^|[^a-zA-Z0-9_])1\.0\.[0-9]+" frontend/src --include="*.vue" --include="*.ts" --include="*.js" 2>/dev/null | grep -v "import.meta.env" | grep -qv "version"; then
  fail "前端源码存在硬编码版本串，应使用 VITE_APP_VERSION"
fi

step "lockfile and build"
if command -v npm >/dev/null 2>&1; then
  (cd frontend && npm ci --include=optional) || fail "npm ci 失败"
  [ -f "$PAYLOAD/frontend/dist/index.html" ] || fail "frontend dist missing"
else
  echo "SKIP: npm 不可用，lockfile 真实性与构建留待 Node/CI 补证" >&2
fi

cd "$ROOT"
echo "step: baseline gate"
if ! "${PYTHON_BIN:-python3}" scripts/check_baseline.py --baseline scripts/release_baseline.json; then
  fail "见 check_baseline.py 输出"
fi
echo "payload ready: $PAYLOAD (upload is manual)"
