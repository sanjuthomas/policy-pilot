package instruction.lifecycle

has_role(role) if {
    role in input.subject.roles
}

# True when the acting subject is a member of the named ZITADEL group.
in_group(group) if {
    group in input.subject.groups
}

# ---------------------------------------------------------------------------
# INSTRUCTION_VIEWER — implicit grant rules
#
# A subject has instruction viewer access if they hold any of:
#   • INSTRUCTION_VIEWER  — explicit read-only grant
#   • INSTRUCTION_CREATOR — creators can always read instructions
#   • INSTRUCTION_APPROVER — approvers can always read instructions
#   • PAYMENT_CREATOR — payment staff must be able to read instructions
#                       to validate them before creating a payment
# ---------------------------------------------------------------------------

has_viewer_access if { has_role("INSTRUCTION_VIEWER") }
has_viewer_access if { has_role("INSTRUCTION_CREATOR") }
has_viewer_access if { has_role("INSTRUCTION_APPROVER") }
has_viewer_access if { has_role("PAYMENT_CREATOR") }
has_viewer_access if { has_role("FUNDING_APPROVER") }

# A subject covers a LOB only when they are MIDDLE_OFFICE and that LOB is in
# covering_lobs. Front-office / desk users do not cover LOBs — they use subject.lob.
covers_lob(lob) if {
	is_middle_office
	lob in input.subject.covering_lobs
}

# Data-level entitlement for instruction read (VIEW / USE / RELEASE_USE).
# Role alone is not enough:
#   • MIDDLE_OFFICE → owning_lob must be in covering_lobs (no desk lob)
#   • everyone else → subject.lob must equal owning_lob
#   • creator of the instruction
#   • platform admin
can_view_instruction_data if {
	is_middle_office
	covers_lob(input.instruction.owning_lob)
}

can_view_instruction_data if {
	not is_middle_office
	same_lob_as_instruction
}

can_view_instruction_data if {
	input.subject.user_id == input.instruction.created_by.user_id
}

can_view_instruction_data if {
	has_role("PLATFORM_ADMIN")
}

can_view_instruction_data if {
	in_group("ADMIN")
}

is_middle_office if {
    "MIDDLE_OFFICE" in input.subject.groups
}

creator_eligible if {
    input.subject.title in {
        "Analyst",
        "Associate",
        "Vice President",
        "Managing Director"
    }
}

account_owning_lob_matches_instruction if {
    input.account.owning_lob == input.instruction.owning_lob
}

same_lob_as_instruction if {
    input.subject.lob == input.instruction.owning_lob
}

creator_is_not_approver if {
    input.subject.user_id != input.instruction.created_by.user_id
}

# Blocks A from approving B's instruction when B is A's manager (existing rule).
not_supervisor_of_creator if {
    not input.instruction.created_by.supervisor_id
}

not_supervisor_of_creator if {
    input.instruction.created_by.supervisor_id
    input.subject.user_id != input.instruction.created_by.supervisor_id
}

# Blocks A from approving B's instruction when A reports directly to B,
# i.e. the creator must not be the approver's own supervisor.
approver_not_subordinate_of_creator if {
    not input.subject.supervisor_id
}

approver_not_subordinate_of_creator if {
    input.subject.supervisor_id
    input.instruction.created_by.user_id != input.subject.supervisor_id
}

within_three_year_limit if {
    start := time.parse_rfc3339_ns(input.instruction.effective_date)
    finish := time.parse_rfc3339_ns(input.instruction.end_date)

    finish > start

    finish - start <= time.parse_duration_ns("26280h")
}

not_expired if {
    time.now_ns() < time.parse_rfc3339_ns(input.instruction.end_date)
}

is_valid_profit_center if {
    input.instruction.owning_lob == "FICC"
}

is_valid_profit_center if {
    input.instruction.owning_lob == "FX"
}

is_valid_profit_center if {
    startswith(input.instruction.owning_lob, "DESK_")
}
