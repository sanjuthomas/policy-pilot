package payment.lifecycle

# Real Rego fixtures for segregation-of-duties on APPROVE.
# Run: opa test opa-policy-seed/policies -v
# (CI: openpolicyagent/opa image against /policies)

_approve_base := {
	"action": "APPROVE",
	"subject": {
		"user_id": "pay-201",
		"title": "VP Funding",
		"roles": ["FUNDING_APPROVER"],
		"groups": ["MIDDLE_OFFICE", "UP_TO_1_BILLION_CLUB"],
		"covering_lobs": ["FICC"],
		"supervisor_id": "pay-301",
	},
	"payment": {
		"payment_id": "20260715-FICC-P-1",
		"instruction_id": "20260715-FICC-I-1",
		"instruction_version": 1,
		"status": "SUBMITTED",
		"amount": 1000000,
		"currency": "USD",
		"owning_lob": "FICC",
		"instruction_type": "STANDING",
		"instruction_status": "APPROVED",
		"instruction_end_date": "2099-01-01T00:00:00Z",
		"instruction_owning_lob": "FICC",
		"created_by": {
			"user_id": "pay-101",
			"title": "Analyst",
			"supervisor_id": "pay-201",
		},
	},
}

test_self_approval_violation_when_creator_approves if {
	input_data := object.union(_approve_base, {
		"subject": object.union(_approve_base.subject, {"user_id": "pay-101"}),
	})
	violations["SELF_APPROVAL"] with input as input_data
}

test_self_approval_absent_when_different_approver if {
	not violations["SELF_APPROVAL"] with input as _approve_base
}

test_allow_false_when_creator_is_approver if {
	input_data := object.union(_approve_base, {
		"subject": object.union(_approve_base.subject, {"user_id": "pay-101"}),
	})
	not allow with input as input_data
}

test_allow_true_for_eligible_funding_approver if {
	allow with input as _approve_base
}

test_reporting_line_violation_when_approver_reports_to_creator if {
	input_data := object.union(_approve_base, {
		"subject": object.union(_approve_base.subject, {
			"user_id": "pay-150",
			"supervisor_id": "pay-101",
		}),
	})
	violations["ALERT_SUBORDINATE_APPROVING_CREATOR"] with input as input_data
	not allow with input as input_data
}
