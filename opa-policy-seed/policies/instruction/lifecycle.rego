package instruction.lifecycle

default allow := false

#
# CREATE — middle office creates on behalf of a profit center
#

allow if {
	input.action == "CREATE"

	catalog_role_ok
	catalog_group_ok

	creator_eligible

	account_owning_lob_matches_instruction

	is_valid_profit_center

	input.instruction.status == "DRAFT"

	input.instruction.type in {
		"STANDING",
		"SINGLE_USE"
	}

	within_three_year_limit
}

#
# UPDATE — middle office edits draft instructions
#

allow if {
	input.action == "UPDATE"

	catalog_role_ok
	catalog_group_ok

	creator_eligible

	account_owning_lob_matches_instruction

	is_valid_profit_center

	input.instruction.status == "DRAFT"

	within_three_year_limit
}

#
# CANCEL — cancel draft or submitted instructions only
#

allow if {
	input.action == "CANCEL"

	catalog_role_ok
	catalog_group_ok

	creator_eligible

	account_owning_lob_matches_instruction

	is_valid_profit_center

	valid_transition
}

#
# SUBMIT — middle office submits
#

allow if {
	input.action == "SUBMIT"

	catalog_role_ok
	catalog_group_ok

	valid_transition
}

#
# APPROVE — profit center approver
#

allow if {
	input.action == "APPROVE"

	catalog_role_ok
	catalog_group_ok

	same_lob_as_instruction

	is_valid_profit_center

	valid_transition

	creator_is_not_approver

	not_supervisor_of_creator

	approver_not_subordinate_of_creator

	approver_is_allowed

	within_three_year_limit
}

#
# REJECT
#

allow if {
	input.action == "REJECT"

	catalog_role_ok
	catalog_group_ok

	same_lob_as_instruction

	is_valid_profit_center

	valid_transition
}

#
# SUSPEND
#

allow if {
	input.action == "SUSPEND"

	catalog_role_ok
	catalog_group_ok

	input.subject.title == "Managing Director"

	same_lob_as_instruction

	is_valid_profit_center

	valid_transition
}

#
# REACTIVATE
#

allow if {
	input.action == "REACTIVATE"

	catalog_role_ok
	catalog_group_ok

	same_lob_as_instruction

	is_valid_profit_center

	valid_transition

	input.subject.user_id != input.instruction.suspended_by
}

#
# USE — mark an instruction as used during payment creation
#
# Not in action_catalog (service OBO path); keep explicit role checks.
#

allow if {
	input.action == "USE"

	"INSTRUCTION_MARKER" in input.subject.delegated_by_roles

	has_viewer_access

	can_view_instruction_data

	is_valid_profit_center

	not_expired

	input.instruction.status == "APPROVED"
}

#
# RELEASE_USE — revert a SINGLE_USE instruction from USED back to APPROVED
#

allow if {
	input.action == "RELEASE_USE"

	"INSTRUCTION_MARKER" in input.subject.delegated_by_roles

	has_viewer_access

	can_view_instruction_data

	is_valid_profit_center

	input.instruction.status == "USED"
	input.instruction.type == "SINGLE_USE"
}

#
# VIEW
#

allow if {
	input.action == "VIEW"

	has_viewer_access

	can_view_instruction_data

	is_valid_profit_center
}
