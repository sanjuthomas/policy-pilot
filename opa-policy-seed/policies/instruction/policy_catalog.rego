package instruction.lifecycle

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
		"title": "Instruction creation",
		"narrative": "Someone with the INSTRUCTION_CREATOR role who belongs to the MIDDLE_OFFICE group, with an eligible creator title, may create a DRAFT instruction for a valid profit-center LOB when the account LOB matches and the duration is within three years.",
		"role": "INSTRUCTION_CREATOR",
		"group": "MIDDLE_OFFICE",
		"extra_requires": [
			{"kind": "title", "value": "creator title Analyst through Managing Director"},
			{"kind": "lob", "value": "account owning_lob matches instruction owning_lob; valid profit center"},
			{"kind": "duration", "value": "effective to end date positive and <= 3 years"},
		],
		"gate_predicates": [
			"creator_eligible",
			"account_owning_lob_matches_instruction",
			"is_valid_profit_center",
			"within_three_year_limit",
		],
	},
	"UPDATE": {
		"title": "Instruction draft update",
		"narrative": "Same middle-office creator scope as CREATE, limited to instructions still in DRAFT.",
		"role": "INSTRUCTION_CREATOR",
		"group": "MIDDLE_OFFICE",
		"extra_requires": [
			{"kind": "title", "value": "creator title Analyst through Managing Director"},
			{"kind": "status", "value": "instruction status DRAFT"},
		],
		"gate_predicates": [
			"creator_eligible",
			"account_owning_lob_matches_instruction",
			"is_valid_profit_center",
			"within_three_year_limit",
		],
	},
	"SUBMIT": {
		"title": "Instruction submission",
		"narrative": "A middle-office INSTRUCTION_CREATOR may submit a DRAFT instruction for profit-center approval.",
		"role": "INSTRUCTION_CREATOR",
		"group": "MIDDLE_OFFICE",
		"extra_requires": [
			{"kind": "status", "value": "valid DRAFT to SUBMITTED transition"},
		],
		"gate_predicates": [
			"valid_transition",
		],
	},
	"APPROVE": {
		"title": "Instruction approval",
		"narrative": "Someone with the INSTRUCTION_APPROVER role whose desk lob matches the instruction owning LOB, and whose title is senior enough per the approval matrix relative to the creator, may approve — subject to four-eyes and reporting-line checks.",
		"role": "INSTRUCTION_APPROVER",
		"extra_requires": [
			{"kind": "lob", "value": "subject.lob equals instruction owning LOB"},
			{"kind": "title_matrix", "value": "approver title senior to creator per approval matrix"},
			{"kind": "sod", "value": "approver is not the instruction creator"},
			{"kind": "reporting_line", "value": "neither supervisor approving subordinate nor subordinate approving manager"},
			{"kind": "duration", "value": "instruction duration still within three-year limit"},
		],
		"gate_predicates": [
			"same_lob_as_instruction",
			"is_valid_profit_center",
			"valid_transition",
			"creator_is_not_approver",
			"not_supervisor_of_creator",
			"approver_not_subordinate_of_creator",
			"approver_is_allowed",
			"within_three_year_limit",
		],
	},
	"REJECT": {
		"title": "Instruction rejection",
		"narrative": "An INSTRUCTION_APPROVER on the same desk LOB may reject a submitted instruction.",
		"role": "INSTRUCTION_APPROVER",
		"extra_requires": [
			{"kind": "lob", "value": "subject.lob equals instruction owning LOB"},
			{"kind": "status", "value": "valid state transition for REJECT"},
		],
		"gate_predicates": [
			"same_lob_as_instruction",
			"is_valid_profit_center",
			"valid_transition",
		],
	},
	"SUSPEND": {
		"title": "Instruction suspension",
		"narrative": "A Managing Director with INSTRUCTION_APPROVER on the same desk LOB may suspend an approved instruction.",
		"role": "INSTRUCTION_APPROVER",
		"extra_requires": [
			{"kind": "title", "value": "Managing Director"},
			{"kind": "lob", "value": "subject.lob equals instruction owning LOB"},
		],
		"gate_predicates": [
			"same_lob_as_instruction",
			"is_valid_profit_center",
			"valid_transition",
		],
	},
	"REACTIVATE": {
		"title": "Instruction reactivation",
		"narrative": "An INSTRUCTION_APPROVER on the same desk may reactivate a suspended instruction, but not the same user who suspended it.",
		"role": "INSTRUCTION_APPROVER",
		"extra_requires": [
			{"kind": "lob", "value": "subject.lob equals instruction owning LOB"},
			{"kind": "sod", "value": "reactivator is not the user who suspended the instruction"},
		],
		"gate_predicates": [
			"same_lob_as_instruction",
			"is_valid_profit_center",
			"valid_transition",
		],
	},
	"CANCEL": {
		"title": "Instruction cancellation",
		"narrative": "A middle-office INSTRUCTION_CREATOR may cancel an instruction while it is still DRAFT or SUBMITTED.",
		"role": "INSTRUCTION_CREATOR",
		"group": "MIDDLE_OFFICE",
		"extra_requires": [
			{"kind": "status", "value": "instruction status DRAFT or SUBMITTED"},
		],
		"gate_predicates": [
			"creator_eligible",
			"account_owning_lob_matches_instruction",
			"is_valid_profit_center",
			"valid_transition",
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
