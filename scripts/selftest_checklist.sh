#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$ROOT/backend/app/_selftest_mypy_violation.py"
trap 'rm -f "$TMP"' EXIT INT TERM
cat >"$TMP" <<'PY'
def f(x: int) -> int:
    return x + "a"
PY
if "${PYTHON_BIN:-python3}" scripts/check_baseline.py --baseline scripts/release_baseline.json >/dev/null 2>&1; then
  echo "FAIL: selftest 未拦截新增 mypy 错误" >&2
  exit 1
fi
rm -f "$TMP"
FAKE="$ROOT/frontend/pnpm-lock.yaml"
printf '# fake
' >"$FAKE"
trap 'rm -f "$TMP" "$FAKE"' EXIT INT TERM
if "${PYTHON_BIN:-python3}" scripts/check_baseline.py --baseline scripts/release_baseline.json >/dev/null 2>&1; then
  echo "FAIL: selftest 未拦截伪造 pnpm-lock.yaml" >&2
  exit 1
fi
rm -f "$FAKE"; trap - EXIT
"${PYTHON_BIN:-python3}" scripts/check_baseline.py --baseline scripts/release_baseline.json
echo "selftest: PASS"
