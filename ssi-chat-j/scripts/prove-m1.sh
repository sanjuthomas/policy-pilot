#!/usr/bin/env bash
# Deprecated alias — use prove-eligibility.sh (three eligibility goldens).
set -euo pipefail
exec "$(cd "$(dirname "$0")" && pwd)/prove-eligibility.sh" "$@"
