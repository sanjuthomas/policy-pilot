package instruction.lifecycle

valid_transition if {
    input.action == "UPDATE"
    input.instruction.status == "DRAFT"
}

valid_transition if {
    input.action == "DELETE"
    input.instruction.status in {
        "DRAFT",
        "SUBMITTED"
    }
}

valid_transition if {
    input.action == "SUBMIT"
    input.instruction.status == "DRAFT"
}

valid_transition if {
    input.action == "APPROVE"
    input.instruction.status == "SUBMITTED"
}

valid_transition if {
    input.action == "REJECT"
    input.instruction.status == "SUBMITTED"
}

valid_transition if {
    input.action == "SUSPEND"
    input.instruction.status == "APPROVED"
}

valid_transition if {
    input.action == "REACTIVATE"
    input.instruction.status == "SUSPENDED"
}
