package instruction.lifecycle

default allow := false

#
# CREATE — middle office creates on behalf of a profit center
#

allow if {
    input.action == "CREATE"

    has_role("INSTRUCTION_CREATOR")

    is_middle_office

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

    has_role("INSTRUCTION_CREATOR")

    is_middle_office

    creator_eligible

    account_owning_lob_matches_instruction

    is_valid_profit_center

    input.instruction.status == "DRAFT"

    within_three_year_limit
}

#
# DELETE — soft delete draft or submitted instructions only
#

allow if {
    input.action == "DELETE"

    has_role("INSTRUCTION_CREATOR")

    is_middle_office

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

    has_role("INSTRUCTION_CREATOR")

    is_middle_office

    valid_transition
}

#
# APPROVE — profit center approver
#

allow if {
    input.action == "APPROVE"

    has_role("INSTRUCTION_APPROVER")

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

    has_role("INSTRUCTION_APPROVER")

    same_lob_as_instruction

    is_valid_profit_center

    valid_transition
}

#
# SUSPEND
#

allow if {
    input.action == "SUSPEND"

    has_role("INSTRUCTION_APPROVER")

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

    has_role("INSTRUCTION_APPROVER")

    same_lob_as_instruction

    is_valid_profit_center

    valid_transition

    input.subject.user_id != input.instruction.suspended_by
}

#
# USE — mark an instruction as used during payment creation
#
# This action is exclusively reserved for authorised service accounts operating
# via On-Behalf-Of delegation.  Direct calls from human users are always denied
# because input.subject.delegated_by_roles is an empty list for non-OBO requests.
#
# Two independent checks must both pass:
#
#   1. SERVICE CHECK — the calling service account must hold the INSTRUCTION_MARKER
#      role.  Only svc-payment carries this role; no human user does.
#
#   2. USER CHECK — the human on whose behalf the service is acting must have
#      at least read access to the instruction (has_viewer_access).  This ensures
#      that the payment creator genuinely has the right to read the instruction
#      they are paying against.
#

allow if {
    input.action == "USE"

    # Service-level gate: only a service with INSTRUCTION_MARKER may call this
    "INSTRUCTION_MARKER" in input.subject.delegated_by_roles

    # User-level gate: the OBO user must be able to read the instruction
    has_viewer_access

    is_valid_profit_center

    not_expired

    input.instruction.status == "APPROVED"
}

#
# VIEW — any holder of INSTRUCTION_VIEWER, INSTRUCTION_CREATOR,
#         INSTRUCTION_APPROVER, or PAYMENT_CREATOR
#
# The instruction must still belong to a valid profit centre so that
# subjects cannot enumerate instructions from arbitrary LOBs they have
# no relationship to.
#

allow if {
    input.action == "VIEW"

    has_viewer_access

    is_valid_profit_center
}
