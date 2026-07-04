package payment.lifecycle

default allow := false

# ---------------------------------------------------------------------------
# CREATE_PAYMENT  (middle-office data entry)
#
# Middle-office analysts enter payments on behalf of a trading desk.
# They must:
#   1. Hold the PAYMENT_CREATOR role.
#   2. Be a member of the MIDDLE_OFFICE group.
#   3. Have the instruction's owning LOB listed in their covering_lobs
#      (desk-coverage assignment in ZITADEL).
#   4. The backing instruction must be approved (status APPROVED)
#      and not expired.
#   5. The payment amount must be positive and within the creator's club ceiling.
#
# The payment enters DRAFT state after creation.
# ---------------------------------------------------------------------------

allow if {
    input.action == "CREATE_PAYMENT"

    has_role("PAYMENT_CREATOR")

    in_group("MIDDLE_OFFICE")
    covers_lob(input.payment.instruction_owning_lob)

    instruction_is_approved

    instruction_not_expired

    input.payment.amount > 0

    within_amount_limit
}

# ---------------------------------------------------------------------------
# UPDATE_PAYMENT  (middle-office edits draft payments)
#
# Same desk-coverage and instruction validity rules as CREATE_PAYMENT.
# Only payments in DRAFT may be edited; each update appends a new version.
# ---------------------------------------------------------------------------

allow if {
    input.action == "UPDATE_PAYMENT"

    has_role("PAYMENT_CREATOR")

    in_group("MIDDLE_OFFICE")
    covers_lob(input.payment.instruction_owning_lob)

    instruction_is_approved

    instruction_not_expired

    input.payment.amount > 0

    input.payment.status == "DRAFT"

    within_amount_limit
}

# ---------------------------------------------------------------------------
# SUBMIT_PAYMENT  (front-office review and hand-off)
#
# A front-office analyst who belongs to the trading desk that owns the
# instruction reviews the draft and submits it for funding approval.
# They must:
#   1. Hold the PAYMENT_CREATOR role.
#   2. Have subject.lob matching the instruction's owning LOB — they are
#      organically part of that desk (front-office identity check).
#      This is intentionally different from CREATE: middle office covers
#      LOBs via an explicit list; front office IS the LOB.
#   3. The instruction must still be approved and not expired.
#
# Submission moves the payment DRAFT → SUBMITTED.
# ---------------------------------------------------------------------------

allow if {
    input.action == "SUBMIT_PAYMENT"

    has_role("PAYMENT_CREATOR")

    input.subject.lob == input.payment.instruction_owning_lob

    instruction_is_approved

    instruction_not_expired
}

# ---------------------------------------------------------------------------
# APPROVE_PAYMENT  (middle-office treasury / funding approval)
#
# Funding approval is a back-office (treasury / middle-office) function.
# The approver must:
#   1. Hold the FUNDING_APPROVER role.
#   2. Be a member of the MIDDLE_OFFICE group.
#   3. Have the instruction's owning LOB in their covering_lobs.
#   4. The instruction must still be approved and not expired.
#      (A service-layer validity check will auto-cancel the payment if the
#       instruction changed since creation.)
#   5. Payment amount within the approver's club ceiling.
#   6. Four-eyes: approver ≠ creator (segregation of duties).
#   7. Approver must not report directly to the creator (reporting-line
#      conflict of interest).
# ---------------------------------------------------------------------------

allow if {
    input.action == "APPROVE_PAYMENT"

    has_role("FUNDING_APPROVER")

    in_group("MIDDLE_OFFICE")
    covers_lob(input.payment.instruction_owning_lob)

    instruction_is_approved

    instruction_not_expired

    within_amount_limit

    payment_creator_is_not_approver

    payment_approver_not_subordinate_of_creator
}

# ---------------------------------------------------------------------------
# REJECT_PAYMENT  (middle-office treasury / funding rejection)
#
# Rejection is symmetric to approval in terms of who is authorised:
# the same middle-office funding team that can approve may also reject.
#   1. Hold the FUNDING_APPROVER role.
#   2. Be a member of the MIDDLE_OFFICE group.
#   3. Have the instruction's owning LOB in their covering_lobs.
#
# No four-eyes or amount-limit constraints apply to rejection — the
# business rationale is that blocking a bad payment is always desirable
# regardless of who raised it.
# ---------------------------------------------------------------------------

allow if {
    input.action == "REJECT_PAYMENT"

    has_role("FUNDING_APPROVER")

    in_group("MIDDLE_OFFICE")
    covers_lob(input.payment.instruction_owning_lob)
}

# ---------------------------------------------------------------------------
# DELETE_PAYMENT  (soft delete draft or submitted payments)
#
# Middle-office payment creators may withdraw a payment before it is approved.
# ---------------------------------------------------------------------------

allow if {
    input.action == "DELETE_PAYMENT"

    has_role("PAYMENT_CREATOR")

    in_group("MIDDLE_OFFICE")
    covers_lob(input.payment.instruction_owning_lob)

    input.payment.status in {"DRAFT", "SUBMITTED"}
}
