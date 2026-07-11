package payment.lifecycle

default allow := false

# ---------------------------------------------------------------------------
# CREATE  (middle-office data entry)
#
# Identity gates (role / group) come from action_catalog; remaining predicates
# must stay listed in action_catalog.CREATE.gate_predicates.
# ---------------------------------------------------------------------------

allow if {
	input.action == "CREATE"

	catalog_role_ok
	catalog_group_ok
	covers_lob(input.payment.instruction_owning_lob)

	instruction_usable_for_draft_payment

	instruction_not_expired

	input.payment.amount > 0

	within_amount_limit
}

# ---------------------------------------------------------------------------
# UPDATE  (middle-office edits draft payments)
# ---------------------------------------------------------------------------

allow if {
	input.action == "UPDATE"

	catalog_role_ok
	catalog_group_ok
	covers_lob(input.payment.instruction_owning_lob)

	instruction_usable_for_draft_payment

	instruction_not_expired

	input.payment.amount > 0

	input.payment.status == "DRAFT"

	within_amount_limit
}

# ---------------------------------------------------------------------------
# SUBMIT  (front-office review and hand-off)
# ---------------------------------------------------------------------------

allow if {
	input.action == "SUBMIT"

	catalog_role_ok
	catalog_group_ok

	input.subject.lob == input.payment.instruction_owning_lob

	instruction_is_approved

	instruction_not_expired
}

# ---------------------------------------------------------------------------
# APPROVE  (middle-office treasury / funding approval)
# ---------------------------------------------------------------------------

allow if {
	input.action == "APPROVE"

	catalog_role_ok
	catalog_group_ok
	covers_lob(input.payment.instruction_owning_lob)

	instruction_backing_valid_for_approval

	instruction_not_expired

	within_amount_limit

	payment_creator_is_not_approver

	payment_approver_not_subordinate_of_creator
}

# ---------------------------------------------------------------------------
# REJECT  (middle-office treasury / funding rejection)
# ---------------------------------------------------------------------------

allow if {
	input.action == "REJECT"

	catalog_role_ok
	catalog_group_ok
	covers_lob(input.payment.instruction_owning_lob)
}

# ---------------------------------------------------------------------------
# CANCEL  (cancel draft or submitted payments)
# ---------------------------------------------------------------------------

allow if {
	input.action == "CANCEL"

	catalog_role_ok
	catalog_group_ok
	covers_lob(input.payment.instruction_owning_lob)

	input.payment.status in {"DRAFT", "SUBMITTED"}
}
