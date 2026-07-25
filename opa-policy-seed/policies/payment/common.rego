package payment.lifecycle

# ---------------------------------------------------------------------------
# Subject helpers
# ---------------------------------------------------------------------------

# True when the acting subject holds the named role.
has_role(role) if {
    role in input.subject.roles
}

# True when the acting subject is a member of the named ZITADEL group.
in_group(group) if {
    group in input.subject.groups
}

# A subject covers a LOB only when they are MIDDLE_OFFICE and that LOB appears in
# covering_lobs. Front-office / desk users never cover LOBs — they match subject.lob.
# Example: MO John covers ["FICC","FX"] → he can act on payments for both desks.
covers_lob(lob) if {
    in_group("MIDDLE_OFFICE")
    lob in input.subject.covering_lobs
}

# ---------------------------------------------------------------------------
# Instruction helpers
# ---------------------------------------------------------------------------

# Submit and funding approval require a fully-approved instruction.
instruction_is_approved if {
    input.payment.instruction_status == "APPROVED"
}

# Draft payments may be created or edited while the backing instruction is still
# progressing through the SSI lifecycle (DRAFT → SUBMITTED → APPROVED).
instruction_usable_for_draft_payment if {
    input.payment.instruction_status in {"DRAFT", "SUBMITTED", "APPROVED"}
}

# After SUBMIT on a SINGLE_USE instruction the saga marks the instruction
# USED before the payment moves to SUBMITTED.  Funding approval must accept that
# consumed state while STANDING instructions remain APPROVED.
instruction_backing_valid_for_approval if {
    instruction_is_approved
}

instruction_backing_valid_for_approval if {
    input.payment.instruction_status == "USED"
    input.payment.instruction_type == "SINGLE_USE"
}

# Instruction must not be expired.
instruction_not_expired if {
    input.payment.instruction_end_date != ""
    time.now_ns() < time.parse_rfc3339_ns(input.payment.instruction_end_date)
}

# No end_date means no expiry constraint.
instruction_not_expired if {
    input.payment.instruction_end_date == ""
}

# ---------------------------------------------------------------------------
# Payment helpers
# ---------------------------------------------------------------------------

# Human-readable USD for allow_basis — avoid %v scientific notation (e.g. 1e+06).
# Matches ssi-chat-j PolicyBasisFormat compact style where practical.
amount_label := label if {
	amount := to_number(input.payment.amount)
	amount >= 1000000000
	billions := amount / 1000000000
	billions == floor(billions)
	label := sprintf("$%v billion", [billions])
}

amount_label := label if {
	amount := to_number(input.payment.amount)
	amount >= 1000000000
	billions := amount / 1000000000
	billions != floor(billions)
	label := sprintf("$%.1f billion", [billions])
}

amount_label := label if {
	amount := to_number(input.payment.amount)
	amount >= 1000000
	amount < 1000000000
	millions := amount / 1000000
	millions == floor(millions)
	label := sprintf("$%v million", [millions])
}

amount_label := label if {
	amount := to_number(input.payment.amount)
	amount >= 1000000
	amount < 1000000000
	millions := amount / 1000000
	millions != floor(millions)
	label := sprintf("$%.1f million", [millions])
}

amount_label := label if {
	amount := to_number(input.payment.amount)
	amount >= 1000
	amount < 1000000
	label := sprintf("$%.0f", [amount])
}

amount_label := label if {
	amount := to_number(input.payment.amount)
	amount < 1000
	amount == floor(amount)
	label := sprintf("$%v", [amount])
}

amount_label := label if {
	amount := to_number(input.payment.amount)
	amount < 1000
	amount != floor(amount)
	label := sprintf("$%.2f", [amount])
}

# Segregation of duties: the person who created the payment cannot also be
# its approver.
payment_creator_is_not_approver if {
    input.subject.user_id != input.payment.created_by.user_id
}

# Reporting-line conflict: a FUNDING_APPROVER who reports directly to the
# payment creator must not approve that payment.  Having a manager approve
# a subordinate's payment creates a chain-of-command conflict of interest.
payment_approver_not_subordinate_of_creator if {
    not input.subject.supervisor_id
}

payment_approver_not_subordinate_of_creator if {
    input.subject.supervisor_id
    input.payment.created_by.user_id != input.subject.supervisor_id
}
