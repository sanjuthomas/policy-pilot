package instruction.lifecycle

# ---------------------------------------------------------------------------
# allow_basis — human-readable reasons returned when allow=true.
#
# instruction-service queries /v1/data/instruction/lifecycle/allow_basis and persists each
# entry on the success SecurityEvent (details.authorization).
# ---------------------------------------------------------------------------

# ── CREATE / UPDATE / CANCEL / SUBMIT (creator actions) ───────────────────────

allow_basis contains "role INSTRUCTION_CREATOR" if {
    input.action in {"CREATE", "UPDATE", "CANCEL", "SUBMIT"}
    has_role("INSTRUCTION_CREATOR")
}

allow_basis contains "group MIDDLE_OFFICE" if {
    input.action in {"CREATE", "UPDATE", "CANCEL", "SUBMIT"}
    is_middle_office
}

allow_basis contains msg if {
    input.action in {"CREATE", "UPDATE", "CANCEL", "SUBMIT"}
    creator_eligible
    msg := sprintf("creator title %v eligible", [input.subject.title])
}

allow_basis contains msg if {
    input.action in {"CREATE", "UPDATE", "CANCEL"}
    account_owning_lob_matches_instruction
    msg := sprintf("account LOB matches instruction LOB %v", [input.instruction.owning_lob])
}

allow_basis contains msg if {
    input.action in {"CREATE", "UPDATE", "CANCEL", "SUBMIT", "APPROVE", "REJECT", "SUSPEND", "REACTIVATE", "VIEW", "USE", "RELEASE_USE"}
    is_valid_profit_center
    msg := sprintf("valid profit center LOB %v", [input.instruction.owning_lob])
}

allow_basis contains msg if {
    input.action in {"CREATE", "UPDATE", "APPROVE"}
    within_three_year_limit
    msg := "instruction duration within three-year limit"
}

allow_basis contains msg if {
    input.action in {"UPDATE", "CANCEL", "SUBMIT", "APPROVE", "REJECT", "SUSPEND", "REACTIVATE"}
    valid_transition
    msg := sprintf("valid transition for status %v", [input.instruction.status])
}

# ── APPROVE ───────────────────────────────────────────────────────────────────

allow_basis contains "role INSTRUCTION_APPROVER" if {
    input.action == "APPROVE"
    has_role("INSTRUCTION_APPROVER")
}

allow_basis contains msg if {
    input.action == "APPROVE"
    same_lob_as_instruction
    msg := sprintf("approver LOB %v matches instruction LOB", [input.subject.lob])
}

allow_basis contains "not self-approval (creator is not approver)" if {
    input.action == "APPROVE"
    creator_is_not_approver
}

allow_basis contains "approver is not supervisor of creator" if {
    input.action == "APPROVE"
    not_supervisor_of_creator
}

allow_basis contains "approver does not report to creator" if {
    input.action == "APPROVE"
    approver_not_subordinate_of_creator
}

allow_basis contains msg if {
    input.action == "APPROVE"
    approver_is_allowed
    msg := sprintf(
        "approval matrix: %v may approve work by %v",
        [input.subject.title, input.instruction.created_by.title],
    )
}

# ── REJECT ────────────────────────────────────────────────────────────────────

allow_basis contains "role INSTRUCTION_APPROVER" if {
    input.action == "REJECT"
    has_role("INSTRUCTION_APPROVER")
}

allow_basis contains msg if {
    input.action == "REJECT"
    same_lob_as_instruction
    msg := sprintf("approver LOB %v matches instruction LOB", [input.subject.lob])
}

# ── SUSPEND ───────────────────────────────────────────────────────────────────

allow_basis contains "role INSTRUCTION_APPROVER" if {
    input.action == "SUSPEND"
    has_role("INSTRUCTION_APPROVER")
}

allow_basis contains "title Managing Director required for suspend" if {
    input.action == "SUSPEND"
    input.subject.title == "Managing Director"
}

allow_basis contains msg if {
    input.action == "SUSPEND"
    same_lob_as_instruction
    msg := sprintf("approver LOB %v matches instruction LOB", [input.subject.lob])
}

# ── REACTIVATE ────────────────────────────────────────────────────────────────

allow_basis contains "role INSTRUCTION_APPROVER" if {
    input.action == "REACTIVATE"
    has_role("INSTRUCTION_APPROVER")
}

allow_basis contains msg if {
    input.action == "REACTIVATE"
    same_lob_as_instruction
    msg := sprintf("approver LOB %v matches instruction LOB", [input.subject.lob])
}

allow_basis contains "suspender is not reactivator" if {
    input.action == "REACTIVATE"
    input.subject.user_id != input.instruction.suspended_by
}

# ── USE (OBO service) ─────────────────────────────────────────────────────────

allow_basis contains "delegating service has INSTRUCTION_MARKER role" if {
    input.action == "USE"
    "INSTRUCTION_MARKER" in input.subject.delegated_by_roles
}

allow_basis contains "OBO user has instruction viewer access" if {
    input.action == "USE"
    has_viewer_access
}

allow_basis contains sprintf("covers instruction LOB %v", [input.instruction.owning_lob]) if {
    input.action == "USE"
    covers_lob(input.instruction.owning_lob)
}

allow_basis contains sprintf("subject LOB %v matches instruction LOB", [input.subject.lob]) if {
    input.action == "USE"
    same_lob_as_instruction
}

allow_basis contains "instruction not expired" if {
    input.action == "USE"
    not_expired
}

allow_basis contains "instruction status APPROVED" if {
    input.action == "USE"
    input.instruction.status == "APPROVED"
}

# ── RELEASE_USE (OBO service) ───────────────────────────────────────────────────

allow_basis contains "delegating service has INSTRUCTION_MARKER role" if {
    input.action == "RELEASE_USE"
    "INSTRUCTION_MARKER" in input.subject.delegated_by_roles
}

allow_basis contains "OBO user has instruction viewer access" if {
    input.action == "RELEASE_USE"
    has_viewer_access
}

allow_basis contains "instruction status USED and type SINGLE_USE" if {
    input.action == "RELEASE_USE"
    input.instruction.status == "USED"
    input.instruction.type == "SINGLE_USE"
}

# ── VIEW ──────────────────────────────────────────────────────────────────────

allow_basis contains "subject has instruction viewer access" if {
    input.action == "VIEW"
    has_viewer_access
}

allow_basis contains sprintf("subject LOB %v matches instruction LOB", [input.subject.lob]) if {
    input.action == "VIEW"
    same_lob_as_instruction
}

allow_basis contains sprintf("covers instruction LOB %v", [input.instruction.owning_lob]) if {
    input.action == "VIEW"
    covers_lob(input.instruction.owning_lob)
}

allow_basis contains "subject is the instruction creator" if {
    input.action == "VIEW"
    input.subject.user_id == input.instruction.created_by.user_id
}

allow_basis contains "platform admin" if {
    input.action == "VIEW"
    has_role("PLATFORM_ADMIN")
}

allow_basis contains "platform admin" if {
    input.action == "VIEW"
    in_group("ADMIN")
}
