#!/usr/bin/env bash
# Prove ssi-chat-j eligibility goldens against :8096 (HTTP black-box).
# Cases live under ssi-chat-j/eval/ — not loaded by the Java runtime.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CHAT_URL="${CHAT_BASE_URL:-http://localhost:8096}"
GOLDEN="${ROOT}/ssi-chat-j/eval/eligibility_golden.yaml"
IDS="${ELIGIBILITY_GOLDEN_IDS:-golden_policies_eligible_approvers_payment,golden_policies_eligible_submitters_payment,golden_policies_eligible_approvers_instruction,golden_policies_amount_club_directory,golden_policies_covering_lob_directory,golden_policies_instruction_approval_summary,golden_policies_payment_approval_summary,golden_policies_payment_create_summary,golden_policies_payment_cancel_summary,golden_policies_amount_club_inclusive_1b,golden_policies_amount_and_covering_combo,golden_me_who_am_i_identity_tokens_pay205,golden_me_my_permissions_pay205,golden_me_can_create_payment_yes_pay205,golden_me_can_create_payment_fo_submitter,golden_me_who_covers_lob_ficc,golden_me_who_can_create_payment_ficc,golden_me_users_like_me_pay205,golden_me_can_approve_payment_capability,golden_me_can_submit_payment_fo_fx,golden_me_who_can_create_instruction,golden_me_waiting_for_me_not_approver_fo,golden_me_waiting_for_me_worklist_pay205,golden_me_who_else_can_act_need_id,golden_me_who_else_can_act_submitted,golden_me_can_approve_instruction_no_pay205,golden_me_can_approve_instruction_yes_ficc300,golden_me_can_create_instruction_no_pay205,golden_me_can_create_instruction_yes_mo,golden_me_can_approve_payment_no_fo,golden_instruction_show_by_id_with_noun,golden_instruction_show_by_id_bare,golden_payment_show_by_id_with_noun,golden_payment_show_by_id_bare,golden_instruction_show_by_id_not_found,golden_payment_show_by_id_not_found,golden_instruction_show_by_id_forbidden_fo,golden_payment_show_by_id_forbidden_fo}"

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
