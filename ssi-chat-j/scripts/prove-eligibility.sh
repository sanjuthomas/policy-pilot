#!/usr/bin/env bash
# Prove ssi-chat-j eligibility goldens against :8096 (HTTP black-box).
# Cases live under ssi-chat-j/eval/ — not loaded by the Java runtime.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CHAT_URL="${CHAT_BASE_URL:-http://localhost:8096}"
GOLDEN="${ROOT}/ssi-chat-j/eval/eligibility_golden.yaml"
IDS="${ELIGIBILITY_GOLDEN_IDS:-golden_policies_eligible_approvers_payment,golden_policies_eligible_submitters_payment,golden_policies_eligible_approvers_instruction,golden_policies_amount_club_directory,golden_policies_covering_lob_directory,golden_policies_instruction_approval_summary,golden_policies_payment_approval_summary,golden_policies_payment_create_summary,golden_policies_payment_cancel_summary,golden_policies_amount_club_inclusive_1b,golden_policies_amount_and_covering_combo,golden_me_who_am_i_identity_tokens_pay205,golden_me_my_permissions_pay205,golden_me_can_create_payment_yes_pay205,golden_me_can_create_payment_fo_submitter,golden_me_who_covers_lob_ficc,golden_me_who_can_create_payment_ficc,golden_me_users_like_me_pay205,golden_me_can_approve_payment_capability,golden_me_can_submit_payment_fo_fx,golden_me_who_can_create_instruction,golden_me_waiting_for_me_not_approver_fo,golden_me_waiting_for_me_worklist_pay205,golden_me_who_else_can_act_submitted,golden_me_can_approve_instruction_no_pay205,golden_me_can_approve_instruction_yes_ficc300,golden_me_can_create_instruction_no_pay205,golden_me_can_create_instruction_yes_mo,golden_me_can_approve_payment_no_fo,golden_instruction_show_by_id_with_noun,golden_instruction_show_by_id_bare,golden_payment_show_by_id_with_noun,golden_payment_show_by_id_bare,golden_instruction_show_by_id_not_found,golden_payment_show_by_id_not_found,golden_instruction_show_by_id_forbidden_fo,golden_payment_show_by_id_forbidden_fo,golden_events_count_today,golden_instruction_denials_count_week,golden_instruction_denials_list_week,golden_payment_denials_count_today,golden_alerts_list_today_entity_ids,golden_events_top_denial_user,golden_fo_fx_instruction_denials_scoped,golden_fo_fx_payment_denials_scoped,golden_fo_ficc_instruction_denials_positive,golden_payment_status,golden_instruction_status,golden_payment_creator,golden_instruction_creator,golden_payment_creator_and_approver,golden_instruction_creator_and_approver,golden_instructions_list_by_status,golden_instructions_list_standing,golden_instructions_list_single_use,golden_instructions_created_by_user,golden_instruction_versions,golden_payment_versions,golden_events_who_approved_payment,golden_instruction_who_approved,golden_instruction_view_fo_ficc,golden_instruction_view_mo_covering_ficc,golden_vector_security_summary,golden_person_permissions_kowalski,golden_instructions_self_approval,golden_instructions_subordinate_approver,golden_instructions_duplicate_routes,golden_instructions_mutual_approval,golden_cross_entity_reciprocal_approval,golden_events_instruction_timeline}"

echo "=== health ${CHAT_URL} ==="
curl -sf "${CHAT_URL}/health" | tee /dev/stderr | grep -q UP

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  PYTHON=python
fi

# Demo SoD rewires (policy-only seed cannot produce these via OPA). Soft goldens still
# accept empty answers; seeding makes positive mutual/cross rows available when present.
if [[ ",${IDS}," == *",golden_instructions_mutual_approval,"* ]] \
  || [[ ",${IDS}," == *",golden_cross_entity_reciprocal_approval,"* ]]; then
  echo "=== SoD demo seeds (mutual / cross-entity) ==="
  if [[ ",${IDS}," == *",golden_instructions_mutual_approval,"* ]]; then
    "$PYTHON" "${ROOT}/ssi-demo-harness/seed_mutual_approval.py" || true
  fi
  if [[ ",${IDS}," == *",golden_cross_entity_reciprocal_approval,"* ]]; then
    "$PYTHON" "${ROOT}/ssi-demo-harness/seed_cross_entity_reciprocal.py" || true
  fi
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
