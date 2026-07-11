package payment.lifecycle

# ---------------------------------------------------------------------------
# policy_summary — derived from action_catalog (no duplicated role/group lists).
#
# Queried via GET /v1/data/payment/lifecycle/policy_summary (no input).
# ---------------------------------------------------------------------------

policy_summary := {
	"domain": "payment",
	"actions": {action: summary_entry(action) |
		some action
		action_catalog[action]
	},
}

summary_entry(action) := {
	"title": action_catalog[action].title,
	"narrative": action_catalog[action].narrative,
	"requires": requires_for(action),
}

requires_for(action) := array.concat(
	array.concat(
		[{"kind": "role", "value": action_catalog[action].role}],
		group_requires(action),
	),
	object.get(action_catalog[action], "extra_requires", []),
)

group_requires(action) := [{"kind": "group", "value": action_catalog[action].group}] if {
	"group" in action_catalog[action]
}

group_requires(action) := [] if {
	not "group" in action_catalog[action]
}
