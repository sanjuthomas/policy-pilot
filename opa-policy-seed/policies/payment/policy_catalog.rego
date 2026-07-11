package payment.lifecycle

# ---------------------------------------------------------------------------
# action_catalog — single source for identity gates + chat policy_summary.
#
# lifecycle.rego reads role/group via catalog_role_ok / catalog_group_ok.
# policy_summary.rego derives title / narrative / requires from this object.
# gate_predicates lists helper names that MUST appear in the matching allow
# rule; opa-policy-seed/validate_policy_catalog.py enforces that.
# ---------------------------------------------------------------------------

action_catalog := {
	"CREATE": {
		"title": "Payment creation",
		"narrative": "Someone with the PAYMENT_CREATOR role who belongs to the MIDDLE_OFFICE group, whose covering_lobs include the instruction's owning LOB, and whose amount-limit club covers the payment amount may create a draft payment against a usable, unexpired instruction.",
		"role": "PAYMENT_CREATOR",
		"group": "MIDDLE_OFFICE",
		"extra_requires": [
			{"kind": "covering_lobs", "value": "instruction owning LOB"},
			{"kind": "amount_club", "value": "subject club ceiling >= payment amount (absolute max $100B)"},
			{"kind": "instruction", "value": "backing instruction DRAFT, SUBMITTED, or APPROVED and not expired"},
		],
		"gate_predicates": [
			"covers_lob",
			"instruction_usable_for_draft_payment",
			"instruction_not_expired",
			"within_amount_limit",
		],
	},
	"UPDATE": {
		"title": "Payment draft update",
		"narrative": "Same middle-office creator scope as CREATE, limited to payments still in DRAFT.",
		"role": "PAYMENT_CREATOR",
		"group": "MIDDLE_OFFICE",
		"extra_requires": [
			{"kind": "covering_lobs", "value": "instruction owning LOB"},
			{"kind": "amount_club", "value": "subject club ceiling >= payment amount (absolute max $100B)"},
			{"kind": "status", "value": "payment status DRAFT"},
		],
		"gate_predicates": [
			"covers_lob",
			"instruction_usable_for_draft_payment",
			"instruction_not_expired",
			"within_amount_limit",
		],
	},
	"SUBMIT": {
		"title": "Payment submission",
		"narrative": "Someone with the PAYMENT_CREATOR role whose desk lob matches the instruction owning LOB may submit a draft payment for funding review when the backing instruction is APPROVED and not expired.",
		"role": "PAYMENT_CREATOR",
		"extra_requires": [
			{"kind": "lob", "value": "subject.lob equals instruction owning LOB"},
			{"kind": "instruction", "value": "backing instruction APPROVED and not expired"},
			{"kind": "status", "value": "payment status DRAFT"},
		],
		"gate_predicates": [
			"instruction_is_approved",
			"instruction_not_expired",
		],
	},
	"APPROVE": {
		"title": "Funding approval",
		"narrative": "Someone with the FUNDING_APPROVER role, who belongs to the MIDDLE_OFFICE group and an amount-limit club, and whose covering_lobs include the instruction's owning LOB, may approve a payment — subject to amount ceilings, four-eyes, and reporting-line checks.",
		"role": "FUNDING_APPROVER",
		"group": "MIDDLE_OFFICE",
		"extra_requires": [
			{"kind": "covering_lobs", "value": "instruction owning LOB"},
			{"kind": "amount_club", "value": "subject club ceiling >= payment amount (absolute max $100B)"},
			{"kind": "instruction", "value": "backing instruction APPROVED (STANDING) or USED (SINGLE_USE), not expired"},
			{"kind": "sod", "value": "approver is not the payment creator"},
			{"kind": "reporting_line", "value": "approver does not report directly to the payment creator"},
		],
		"gate_predicates": [
			"covers_lob",
			"instruction_backing_valid_for_approval",
			"instruction_not_expired",
			"within_amount_limit",
			"payment_creator_is_not_approver",
			"payment_approver_not_subordinate_of_creator",
		],
	},
	"REJECT": {
		"title": "Funding rejection",
		"narrative": "The same middle-office funding team that can approve may reject a payment for a covered LOB; four-eyes and amount-limit checks do not apply to rejection.",
		"role": "FUNDING_APPROVER",
		"group": "MIDDLE_OFFICE",
		"extra_requires": [
			{"kind": "covering_lobs", "value": "instruction owning LOB"},
		],
		"gate_predicates": [
			"covers_lob",
		],
	},
	"CANCEL": {
		"title": "Payment cancellation",
		"narrative": "A middle-office PAYMENT_CREATOR covering the instruction LOB may cancel a payment while it is still DRAFT or SUBMITTED.",
		"role": "PAYMENT_CREATOR",
		"group": "MIDDLE_OFFICE",
		"extra_requires": [
			{"kind": "covering_lobs", "value": "instruction owning LOB"},
			{"kind": "status", "value": "payment status DRAFT or SUBMITTED"},
		],
		"gate_predicates": [
			"covers_lob",
		],
	},
}

catalog_role_ok if {
	has_role(action_catalog[input.action].role)
}

catalog_group_ok if {
	not "group" in action_catalog[input.action]
}

catalog_group_ok if {
	"group" in action_catalog[input.action]
	in_group(action_catalog[input.action].group)
}
