package instruction.lifecycle

# Data-level VIEW entitlement (LOB / covering_lobs).
# Run: opa test opa-policy-seed/policies -v

_instruction := {
	"instruction_id": "20260718-FICC-I-1",
	"status": "APPROVED",
	"type": "STANDING",
	"owning_lob": "FICC",
	"effective_date": "2026-01-01T00:00:00Z",
	"end_date": "2028-01-01T00:00:00Z",
	"created_by": {"user_id": "mo-100"},
}

test_view_allowed_same_lob if {
	allow with input as {
		"action": "VIEW",
		"subject": {
			"user_id": "ficc-300",
			"title": "Vice President",
			"roles": ["INSTRUCTION_APPROVER"],
			"groups": [],
			"lob": "FICC",
			"covering_lobs": [],
		},
		"instruction": _instruction,
		"account": {"owning_lob": "FICC"},
	}
}

test_view_denied_wrong_desk_lob if {
	input_data := {
		"action": "VIEW",
		"subject": {
			"user_id": "fx-300",
			"title": "Vice President",
			"roles": ["INSTRUCTION_APPROVER"],
			"groups": [],
			"lob": "FX",
			"covering_lobs": [],
		},
		"instruction": _instruction,
		"account": {"owning_lob": "FICC"},
	}
	not allow with input as input_data
	violations["INSTRUCTION_LOB_ACCESS_DENIED"] with input as input_data
}

test_view_allowed_covering_lob if {
	allow with input as {
		"action": "VIEW",
		"subject": {
			"user_id": "pay-101",
			"title": "Analyst",
			"roles": ["PAYMENT_CREATOR"],
			"groups": ["MIDDLE_OFFICE"],
			"covering_lobs": ["FICC", "FX"],
		},
		"instruction": _instruction,
		"account": {"owning_lob": "FICC"},
	}
}

test_view_denied_covering_misses_lob if {
	input_data := {
		"action": "VIEW",
		"subject": {
			"user_id": "pay-202",
			"title": "VP",
			"roles": ["FUNDING_APPROVER"],
			"groups": ["MIDDLE_OFFICE"],
			"covering_lobs": ["DESK_RATES"],
		},
		"instruction": _instruction,
		"account": {"owning_lob": "FICC"},
	}
	not allow with input as input_data
	violations["INSTRUCTION_LOB_ACCESS_DENIED"] with input as input_data
}

test_view_allowed_creator_without_lob if {
	allow with input as {
		"action": "VIEW",
		"subject": {
			"user_id": "mo-100",
			"title": "Analyst",
			"roles": ["INSTRUCTION_CREATOR"],
			"groups": ["MIDDLE_OFFICE"],
			"covering_lobs": [],
		},
		"instruction": _instruction,
		"account": {"owning_lob": "FICC"},
	}
}

test_view_denied_role_only_no_bu if {
	input_data := {
		"action": "VIEW",
		"subject": {
			"user_id": "viewer-1",
			"title": "Analyst",
			"roles": ["INSTRUCTION_VIEWER"],
			"groups": [],
			"covering_lobs": [],
		},
		"instruction": _instruction,
		"account": {"owning_lob": "FICC"},
	}
	not allow with input as input_data
	violations["INSTRUCTION_LOB_ACCESS_DENIED"] with input as input_data
}

test_view_denied_fo_covering_ignored if {
	# Front office must match subject.lob; covering_lobs alone is not enough.
	input_data := {
		"action": "VIEW",
		"subject": {
			"user_id": "fo-ficc-101",
			"title": "Desk Analyst",
			"roles": ["PAYMENT_CREATOR"],
			"groups": [],
			"lob": "FX",
			"covering_lobs": ["FICC"],
		},
		"instruction": _instruction,
		"account": {"owning_lob": "FICC"},
	}
	not allow with input as input_data
	violations["INSTRUCTION_LOB_ACCESS_DENIED"] with input as input_data
}

test_view_denied_mo_lob_without_covering if {
	# Middle office has no desk lob entitlement — covering_lobs is required.
	input_data := {
		"action": "VIEW",
		"subject": {
			"user_id": "mo-orphan",
			"title": "Analyst",
			"roles": ["INSTRUCTION_CREATOR"],
			"groups": ["MIDDLE_OFFICE"],
			"lob": "FICC",
			"covering_lobs": [],
		},
		"instruction": _instruction,
		"account": {"owning_lob": "FICC"},
	}
	not allow with input as input_data
	violations["INSTRUCTION_LOB_ACCESS_DENIED"] with input as input_data
}

test_view_allowed_platform_admin if {
	allow with input as {
		"action": "VIEW",
		"subject": {
			"user_id": "admin-001",
			"title": "Platform Administrator",
			"roles": ["PLATFORM_ADMIN", "INSTRUCTION_VIEWER"],
			"groups": ["ADMIN"],
			"covering_lobs": [],
		},
		"instruction": _instruction,
		"account": {"owning_lob": "FICC"},
	}
}
