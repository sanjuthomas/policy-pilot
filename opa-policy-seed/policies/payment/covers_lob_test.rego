package payment.lifecycle

# covering_lobs is MIDDLE_OFFICE-only. Desk/FO users match subject.lob instead.
# Run: opa test opa-policy-seed/policies -v

test_covers_lob_mo_positive if {
	covers_lob("FICC") with input as {
		"subject": {
			"user_id": "pay-101",
			"roles": ["PAYMENT_CREATOR"],
			"groups": ["MIDDLE_OFFICE"],
			"covering_lobs": ["FICC", "FX"],
		},
	}
}

test_covers_lob_mo_negative_misses_lob if {
	not covers_lob("FICC") with input as {
		"subject": {
			"user_id": "pay-203",
			"roles": ["PAYMENT_CREATOR", "FUNDING_APPROVER"],
			"groups": ["MIDDLE_OFFICE"],
			"covering_lobs": ["FX"],
		},
	}
}

test_covers_lob_fo_ignored_even_when_populated if {
	# Front office must never gain entitlement from covering_lobs.
	not covers_lob("FICC") with input as {
		"subject": {
			"user_id": "fo-ficc-101",
			"roles": ["PAYMENT_CREATOR"],
			"groups": [],
			"lob": "FX",
			"covering_lobs": ["FICC"],
		},
	}
}

test_covers_lob_fo_with_matching_desk_lob_still_false if {
	# covers_lob is MO-only; desk match is a separate predicate in callers.
	not covers_lob("FICC") with input as {
		"subject": {
			"user_id": "fo-ficc-101",
			"roles": ["PAYMENT_CREATOR"],
			"groups": [],
			"lob": "FICC",
			"covering_lobs": [],
		},
	}
}
