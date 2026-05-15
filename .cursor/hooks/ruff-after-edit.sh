#!/usr/bin/env bash
# Cursor hook: run Ruff format + check on Python under services/ (mirrors CI check paths).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INPUT=$(cat)

MODE="$(echo "$INPUT" | python3 -c "
import json, sys, os

root = os.path.abspath(sys.argv[1])
try:
    data = json.load(sys.stdin)
except Exception:
    print('SKIP')
    sys.exit(0)
fp = (data.get('file_path') or '').strip()
if not fp.endswith('.py'):
    print('SKIP')
    sys.exit(0)
try:
    abs_fp = os.path.abspath(fp)
except OSError:
    print('SKIP')
    sys.exit(0)
if not abs_fp.startswith(root + os.sep):
    print('SKIP')
    sys.exit(0)
if f'{os.sep}services{os.sep}' not in abs_fp:
    print('SKIP')
    sys.exit(0)
print('RUN')
" "$REPO_ROOT")"

if [[ "${MODE:-SKIP}" != RUN ]]; then
  echo '{}'
  exit 0
fi

cd "$REPO_ROOT"
if ! command -v uv >/dev/null 2>&1; then
  echo '{}' >&2
  exit 0
fi

uv run ruff format services/shared/shared services/web/web services/collector/
uv run ruff check services/shared/shared services/web/web services/collector/

echo '{}'
