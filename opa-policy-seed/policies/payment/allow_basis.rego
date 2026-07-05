package payment.lifecycle

# ---------------------------------------------------------------------------
# allow_basis — human-readable reasons returned when allow=true.
#
# The payment service queries /v1/data/payment/lifecycle/allow_basis and
# persists each entry on the success SecurityEvent (details.authorization).
# ---------------------------------------------------------------------------

# ── CREATE ────────────────────────────────────────────────────────────

allow_basis contains "role PAYMENT_CREATOR" if {
    input.action == "CREATE"
    has_role("PAYMENT_CREATOR")
}

allow_basis contains "group MIDDLE_OFFICE" if {
    input.action == "CREATE"
    in_group("MIDDLE_OFFICE")
}

allow_basis contains msg if {
    input.action == "CREATE"
    covers_lob(input.payment.instruction_owning_lob)
    msg := sprintf("covers LOB %v", [input.payment.instruction_owning_lob])
}

allow_basis contains msg if {
    input.action == "CREATE"
    instruction_usable_for_draft_payment
    msg := sprintf("instruction status %v", [input.payment.instruction_status])
}

allow_basis contains "instruction not expired" if {
    input.action == "CREATE"
    instruction_not_expired
}

allow_basis contains msg if {
    input.action == "CREATE"
    within_amount_limit
    msg := sprintf("amount %v within subject and absolute limits", [input.payment.amount])
}

# ── UPDATE ────────────────────────────────────────────────────────────

allow_basis contains "role PAYMENT_CREATOR" if {
    input.action == "UPDATE"
    has_role("PAYMENT_CREATOR")
}

allow_basis contains "group MIDDLE_OFFICE" if {
    input.action == "UPDATE"
    in_group("MIDDLE_OFFICE")
}

allow_basis contains msg if {
    input.action == "UPDATE"
    covers_lob(input.payment.instruction_owning_lob)
    msg := sprintf("covers LOB %v", [input.payment.instruction_owning_lob])
}

allow_basis contains msg if {
    input.action == "UPDATE"
    instruction_usable_for_draft_payment
    msg := sprintf("instruction status %v", [input.payment.instruction_status])
}

allow_basis contains "instruction not expired" if {
    input.action == "UPDATE"
    instruction_not_expired
}

allow_basis contains "payment status DRAFT" if {
    input.action == "UPDATE"
    input.payment.status == "DRAFT"
}

allow_basis contains msg if {
    input.action == "UPDATE"
    within_amount_limit
    msg := sprintf("amount %v within subject and absolute limits", [input.payment.amount])
}

# ── SUBMIT ────────────────────────────────────────────────────────────

allow_basis contains "role PAYMENT_CREATOR" if {
    input.action == "SUBMIT"
    has_role("PAYMENT_CREATOR")
}

allow_basis contains msg if {
    input.action == "SUBMIT"
    input.subject.lob == input.payment.instruction_owning_lob
    msg := sprintf("desk LOB %v matches instruction LOB", [input.subject.lob])
}

allow_basis contains msg if {
    input.action == "SUBMIT"
    instruction_is_approved
    msg := sprintf("instruction status %v", [input.payment.instruction_status])
}

allow_basis contains "instruction not expired" if {
    input.action == "SUBMIT"
    instruction_not_expired
}

# ── APPROVE ───────────────────────────────────────────────────────────

allow_basis contains "role FUNDING_APPROVER" if {
    input.action == "APPROVE"
    has_role("FUNDING_APPROVER")
}

allow_basis contains "group MIDDLE_OFFICE" if {
    input.action == "APPROVE"
    in_group("MIDDLE_OFFICE")
}

allow_basis contains msg if {
    input.action == "APPROVE"
    covers_lob(input.payment.instruction_owning_lob)
    msg := sprintf("covers LOB %v", [input.payment.instruction_owning_lob])
}

allow_basis contains msg if {
    input.action == "APPROVE"
    instruction_backing_valid_for_approval
    msg := sprintf(
        "instruction status %v type %v",
        [input.payment.instruction_status, input.payment.instruction_type],
    )
}

allow_basis contains "instruction not expired" if {
    input.action == "APPROVE"
    instruction_not_expired
}

allow_basis contains msg if {
    input.action == "APPROVE"
    within_amount_limit
    msg := sprintf("amount %v within subject and absolute limits", [input.payment.amount])
}

allow_basis contains "not self-approval (creator is not approver)" if {
    input.action == "APPROVE"
    payment_creator_is_not_approver
}

allow_basis contains "approver does not report to payment creator" if {
    input.action == "APPROVE"
    payment_approver_not_subordinate_of_creator
}

# ── REJECT ────────────────────────────────────────────────────────────

allow_basis contains "role FUNDING_APPROVER" if {
    input.action == "REJECT"
    has_role("FUNDING_APPROVER")
}

allow_basis contains "group MIDDLE_OFFICE" if {
    input.action == "REJECT"
    in_group("MIDDLE_OFFICE")
}

allow_basis contains msg if {
    input.action == "REJECT"
    covers_lob(input.payment.instruction_owning_lob)
    msg := sprintf("covers LOB %v", [input.payment.instruction_owning_lob])
}
