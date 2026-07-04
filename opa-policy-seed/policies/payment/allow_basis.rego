package payment.lifecycle

# ---------------------------------------------------------------------------
# allow_basis — human-readable reasons returned when allow=true.
#
# The payment service queries /v1/data/payment/lifecycle/allow_basis and
# persists each entry on the success SecurityEvent (details.authorization).
# ---------------------------------------------------------------------------

# ── CREATE_PAYMENT ────────────────────────────────────────────────────────────

allow_basis contains "role PAYMENT_CREATOR" if {
    input.action == "CREATE_PAYMENT"
    has_role("PAYMENT_CREATOR")
}

allow_basis contains "group MIDDLE_OFFICE" if {
    input.action == "CREATE_PAYMENT"
    in_group("MIDDLE_OFFICE")
}

allow_basis contains msg if {
    input.action == "CREATE_PAYMENT"
    covers_lob(input.payment.instruction_owning_lob)
    msg := sprintf("covers LOB %v", [input.payment.instruction_owning_lob])
}

allow_basis contains msg if {
    input.action == "CREATE_PAYMENT"
    instruction_is_approved
    msg := sprintf("instruction status %v", [input.payment.instruction_status])
}

allow_basis contains "instruction not expired" if {
    input.action == "CREATE_PAYMENT"
    instruction_not_expired
}

allow_basis contains msg if {
    input.action == "CREATE_PAYMENT"
    within_amount_limit
    msg := sprintf("amount %v within subject and absolute limits", [input.payment.amount])
}

# ── UPDATE_PAYMENT ────────────────────────────────────────────────────────────

allow_basis contains "role PAYMENT_CREATOR" if {
    input.action == "UPDATE_PAYMENT"
    has_role("PAYMENT_CREATOR")
}

allow_basis contains "group MIDDLE_OFFICE" if {
    input.action == "UPDATE_PAYMENT"
    in_group("MIDDLE_OFFICE")
}

allow_basis contains msg if {
    input.action == "UPDATE_PAYMENT"
    covers_lob(input.payment.instruction_owning_lob)
    msg := sprintf("covers LOB %v", [input.payment.instruction_owning_lob])
}

allow_basis contains msg if {
    input.action == "UPDATE_PAYMENT"
    instruction_is_approved
    msg := sprintf("instruction status %v", [input.payment.instruction_status])
}

allow_basis contains "instruction not expired" if {
    input.action == "UPDATE_PAYMENT"
    instruction_not_expired
}

allow_basis contains "payment status DRAFT" if {
    input.action == "UPDATE_PAYMENT"
    input.payment.status == "DRAFT"
}

allow_basis contains msg if {
    input.action == "UPDATE_PAYMENT"
    within_amount_limit
    msg := sprintf("amount %v within subject and absolute limits", [input.payment.amount])
}

# ── SUBMIT_PAYMENT ────────────────────────────────────────────────────────────

allow_basis contains "role PAYMENT_CREATOR" if {
    input.action == "SUBMIT_PAYMENT"
    has_role("PAYMENT_CREATOR")
}

allow_basis contains msg if {
    input.action == "SUBMIT_PAYMENT"
    input.subject.lob == input.payment.instruction_owning_lob
    msg := sprintf("desk LOB %v matches instruction LOB", [input.subject.lob])
}

allow_basis contains msg if {
    input.action == "SUBMIT_PAYMENT"
    instruction_is_approved
    msg := sprintf("instruction status %v", [input.payment.instruction_status])
}

allow_basis contains "instruction not expired" if {
    input.action == "SUBMIT_PAYMENT"
    instruction_not_expired
}

# ── APPROVE_PAYMENT ───────────────────────────────────────────────────────────

allow_basis contains "role FUNDING_APPROVER" if {
    input.action == "APPROVE_PAYMENT"
    has_role("FUNDING_APPROVER")
}

allow_basis contains "group MIDDLE_OFFICE" if {
    input.action == "APPROVE_PAYMENT"
    in_group("MIDDLE_OFFICE")
}

allow_basis contains msg if {
    input.action == "APPROVE_PAYMENT"
    covers_lob(input.payment.instruction_owning_lob)
    msg := sprintf("covers LOB %v", [input.payment.instruction_owning_lob])
}

allow_basis contains msg if {
    input.action == "APPROVE_PAYMENT"
    instruction_is_approved
    msg := sprintf("instruction status %v", [input.payment.instruction_status])
}

allow_basis contains "instruction not expired" if {
    input.action == "APPROVE_PAYMENT"
    instruction_not_expired
}

allow_basis contains msg if {
    input.action == "APPROVE_PAYMENT"
    within_amount_limit
    msg := sprintf("amount %v within subject and absolute limits", [input.payment.amount])
}

allow_basis contains "not self-approval (creator is not approver)" if {
    input.action == "APPROVE_PAYMENT"
    payment_creator_is_not_approver
}

allow_basis contains "approver does not report to payment creator" if {
    input.action == "APPROVE_PAYMENT"
    payment_approver_not_subordinate_of_creator
}

# ── REJECT_PAYMENT ────────────────────────────────────────────────────────────

allow_basis contains "role FUNDING_APPROVER" if {
    input.action == "REJECT_PAYMENT"
    has_role("FUNDING_APPROVER")
}

allow_basis contains "group MIDDLE_OFFICE" if {
    input.action == "REJECT_PAYMENT"
    in_group("MIDDLE_OFFICE")
}

allow_basis contains msg if {
    input.action == "REJECT_PAYMENT"
    covers_lob(input.payment.instruction_owning_lob)
    msg := sprintf("covers LOB %v", [input.payment.instruction_owning_lob])
}
