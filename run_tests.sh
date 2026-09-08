#!/usr/bin/env bash
# Every test here is offline. Nothing touches YouTube.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
fail=0
for t in tests/test_*.py; do
  echo "── $t"
  python3 "$t" || fail=1
  echo
done
[ $fail -eq 0 ] && echo "all suites passed" || { echo "FAILURES"; exit 1; }
