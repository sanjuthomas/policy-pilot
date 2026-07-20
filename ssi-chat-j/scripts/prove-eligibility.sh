#!/usr/bin/env bash
# Prove ssi-chat-j eligibility goldens against :8096 (HTTP black-box).
# Cases live under ssi-chat-j/eval/ — not loaded by the Java runtime.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CHAT_URL="${CHAT_BASE_URL:-http://localhost:8096}"
GOLDEN="${ROOT}/ssi-chat-j/eval/eligibility_golden.yaml"
IDS="${ELIGIBILITY_GOLDEN_IDS:-golden_policies_eligible_approvers_payment,golden_policies_eligible_submitters_payment,golden_policies_eligible_approvers_instruction}"

echo "=== health ${CHAT_URL} ==="
curl -sf "${CHAT_URL}/health" | tee /dev/stderr | grep -q UP

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  PYTHON=python
fi

echo "=== eligibility golden (${IDS}) via ${GOLDEN} ==="
cd "${ROOT}/ssi-chat"
export CHAT_BASE_URL="${CHAT_URL}"
"$PYTHON" -m regression.runner \
  --eval-golden \
  --golden "${GOLDEN}" \
  --ids "${IDS}" \
  --no-seed \
  --skip-api-smoke \
  --chat-url "${CHAT_URL}"

echo "Eligibility golden OK against ${CHAT_URL}"
