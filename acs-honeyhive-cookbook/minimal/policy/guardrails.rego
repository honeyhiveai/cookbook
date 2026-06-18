package honeyhive.guardrails

import rego.v1

default verdict := {"decision": "allow"}

verdict := pre_tool_call_verdict if { input.intervention_point == "pre_tool_call" }
verdict := output_verdict if { input.intervention_point == "output" }

default pre_tool_call_verdict := {"decision": "allow"}

pre_tool_call_verdict := {
	"decision": "deny",
	"reason": "external_recipient_blocked",
	"message": "Email to external recipients is blocked by policy.",
} if {
	input.tool.name == "send_email"
	args := object.get(input.policy_target, "value", {})
	contains(lower(object.get(args, "to", "")), "@external")
}
else := {
	"decision": "escalate",
	"reason": "high_value_payment",
	"message": "Wire transfers over $1000 require human approval.",
} if {
	input.tool.name == "wire_payment"
	to_number(object.get(object.get(input.policy_target, "value", {}), "amount", 0)) > 1000
}

default output_verdict := {"decision": "allow"}

# NOTE: target is a bare string here, so the transform path is "$policy_target" (the root),
# NOT "$policy_target.value". A wrong root yields runtime_error:transform_invalid.
output_verdict := {
	"decision": "transform",
	"reason": "ssn_redacted",
	"message": "Redacted an SSN-like pattern from the final response.",
	"transform": {
		"path": "$policy_target",
		"value": redacted,
	},
} if {
	text := object.get(input.policy_target, "value", "")
	regex.match(`[0-9]{3}-[0-9]{2}-[0-9]{4}`, text)
	redacted := regex.replace(text, `[0-9]{3}-[0-9]{2}-[0-9]{4}`, "[REDACTED-SSN]")
}
