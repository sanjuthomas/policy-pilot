const executionId = decodeURIComponent(location.pathname.split("/").filter(Boolean).slice(1).join("/"));

function field(label, value) {
  return `<div class="field"><dt>${label}</dt><dd class="mono">${value ?? "—"}</dd></div>`;
}

async function load() {
  document.getElementById("subtitle").textContent = executionId;
  const response = await AuditorAuth.apiFetch(`/api/audit-executions/${encodeURIComponent(executionId)}`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const { execution } = await response.json();
  const actor = execution.actor || {};
  const request = execution.request || {};
  const result = execution.result || {};
  const governance = execution.governance || {};
  const timeline = (execution.timeline || []).map((step) =>
    `<li><strong>${step.step || "step"}${step.decision ? ` · ${step.decision}` : ""}</strong><br>${step.summary || ""}<br><span class="muted mono">${step.at || ""}</span></li>`
  ).join("");
  document.getElementById("summary").innerHTML = `
    <section class="card"><div class="card-header"><h2>${execution.capability || "Audit execution"}</h2><span class="outcome-${execution.outcome}">${execution.outcome || "—"}</span></div>
      <dl class="grid">
        ${field("Status", execution.status)}${field("Actor", actor.user_id)}
        ${field("Roles", (actor.roles || []).join(", "))}${field("Instruction", request.instruction_id)}
        ${field("Amount", request.amount)}${field("Value date", request.value_date)}
        ${field("Payment", result.payment_id)}${field("Security event", governance.security_event_id)}
      </dl>
    </section>
    <section class="card"><div class="card-header"><h2>Timeline</h2></div><ol class="timeline">${timeline || "<li>No steps recorded</li>"}</ol></section>`;
  document.getElementById("json").textContent = JSON.stringify(execution, null, 2);
}

async function loadOpa() {
  const response = await AuditorAuth.apiFetch(`/api/audit-executions/${encodeURIComponent(executionId)}/opa`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const evidence = await response.json();
  document.getElementById("opa-source").textContent =
    evidence.source === "security_event"
      ? `Source: payment security event ${evidence.security_event_id}`
      : evidence.source === "policy_exchange"
        ? "Source: provisional preflight exchange"
        : "No OPA evidence linked";
  document.getElementById("opa-request").textContent = AuditorFormat.prettyJson(
    evidence.evaluate_request || {}
  );
  document.getElementById("opa-response").textContent = AuditorFormat.prettyJson(
    evidence.evaluate_response || {}
  );
  document.getElementById("opa-panel").classList.remove("hidden");
  if (evidence.security_event) {
    document.getElementById("event-json").textContent = AuditorFormat.prettyJson(
      evidence.security_event
    );
    document.getElementById("event-details").classList.remove("hidden");
  }
}

document.getElementById("load-opa").addEventListener("click", () =>
  void loadOpa().catch((error) => {
    document.getElementById("opa-source").textContent = `Load failed: ${error.message}`;
  })
);
AuditorAuth.bind(() => void load().catch((error) => {
  document.getElementById("summary").innerHTML = `<p class="empty">Load failed: ${error.message}</p>`;
}));
