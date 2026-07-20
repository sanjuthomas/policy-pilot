#!/usr/bin/env bash
# Prove M1: golden_policies_eligible_approvers_payment against ssi-chat-j :8096
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CHAT_URL="${CHAT_BASE_URL:-http://localhost:8096}"

echo "=== health ${CHAT_URL} ==="
curl -sf "${CHAT_URL}/health" | tee /dev/stderr | grep -q UP

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  PYTHON=python
fi

echo "=== golden_policies_eligible_approvers_payment ==="
cd "${ROOT}/ssi-chat"
export CHAT_BASE_URL="${CHAT_URL}"
"$PYTHON" -m regression.runner \
  --eval-golden \
  --ids golden_policies_eligible_approvers_payment \
  --no-seed \
  --skip-api-smoke \
  --chat-url "${CHAT_URL}"

echo "M1 proof OK against ${CHAT_URL}"
