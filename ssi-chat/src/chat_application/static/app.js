const thread = document.getElementById("chat-thread");
const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const clearBtn = document.getElementById("clear-btn");
const metaEmpty = document.getElementById("meta-empty");
const metaContent = document.getElementById("meta-content");
const metaTiming = document.getElementById("meta-timing");
const metaCypher = document.getElementById("meta-cypher");
const metaRouting = document.getElementById("meta-routing");
const metaRoutingDetail = document.getElementById("meta-routing-detail");
const metaSources = document.getElementById("meta-sources");
const authStatus = document.getElementById("auth-status");
const authUser = document.getElementById("auth-user");
const authPassword = document.getElementById("auth-password");
const authLoginBtn = document.getElementById("auth-login-btn");
const authLogoutBtn = document.getElementById("auth-logout-btn");

const AUTH_STORAGE_KEY = "ssi-chat-session";
const ASSISTANT_NAME = "PolicyPilot";

/** @type {{ role: 'user' | 'assistant', content: string }[]} */
let history = [];

/** @type {{ user_id: string, session_id: string, session_token: string, audiences?: string[], roles?: string[] } | null} */
let session = null;

/** @type {Map<string, { audiences: string[], roles: string[] }>} */
const chatUserDirectory = new Map();

function loadSession() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    session = raw ? JSON.parse(raw) : null;
  } catch {
    session = null;
  }
  updateAuthUi();
  updateModeVisibility();
}

function saveSession() {
  if (session) {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
  } else {
    localStorage.removeItem(AUTH_STORAGE_KEY);
  }
  updateAuthUi();
  updateModeVisibility();
}

function sessionAudiences() {
  return session?.audiences || [];
}

function isComplianceAudience() {
  return sessionAudiences().includes("compliance");
}

function isOperationalAudience() {
  const audiences = sessionAudiences();
  return (
    audiences.includes("payment_creator") || audiences.includes("funding_approver")
  );
}

function isInstructionAnalystAudience() {
  const audiences = sessionAudiences();
  return (
    audiences.includes("instruction_creator") ||
    audiences.includes("instruction_approver")
  );
}

function canUsePoliciesMode() {
  // Unsigned: show all modes. Signed: compliance, MO/FO payment, instruction analysts.
  return (
    !session ||
    isComplianceAudience() ||
    isOperationalAudience() ||
    isInstructionAnalystAudience()
  );
}

function canUseEventsMode() {
  // Unsigned or compliance: show Security Events. Pure operational users: hide.
  if (!session) {
    return true;
  }
  if (isComplianceAudience()) {
    return true;
  }
  return !isOperationalAudience();
}

function selectFallbackMode(preferredValues) {
  for (const value of preferredValues) {
    const radio = document.querySelector(`input[name="mode"][value="${value}"]`);
    const option = radio?.closest(".mode-option");
    if (radio && option && !option.classList.contains("hidden")) {
      radio.checked = true;
      return;
    }
  }
}

function updateModeVisibility() {
  const policiesOption = document.getElementById("mode-option-policies");
  const eventsOption = document.getElementById("mode-option-events");

  if (policiesOption) {
    const allowPolicies = canUsePoliciesMode();
    policiesOption.classList.toggle("hidden", !allowPolicies);
  }

  if (eventsOption) {
    const allowEvents = canUseEventsMode();
    eventsOption.classList.toggle("hidden", !allowEvents);
  }

  const checked = document.querySelector('input[name="mode"]:checked');
  const checkedOption = checked?.closest(".mode-option");
  if (checkedOption?.classList.contains("hidden")) {
    // Operational users land on Payments; otherwise Events / Instructions.
    selectFallbackMode(["payments", "instructions", "events", "all"]);
  }
}

function updateAuthUi() {
  if (session) {
    authStatus.textContent = `Signed in as ${session.user_id}`;
    authStatus.classList.remove("muted");
    authUser.classList.add("hidden");
    authPassword.classList.add("hidden");
    authLoginBtn.classList.add("hidden");
    authLogoutBtn.classList.remove("hidden");
  } else {
    authStatus.textContent = "Not signed in";
    authStatus.classList.add("muted");
    authUser.classList.remove("hidden");
    authPassword.classList.remove("hidden");
    authLoginBtn.classList.remove("hidden");
    authLogoutBtn.classList.add("hidden");
  }
}

async function loadChatUsers() {
  try {
    const response = await fetch("/api/chat-users");
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    chatUserDirectory.clear();
    for (const user of data.users || []) {
      chatUserDirectory.set(user.user_id, {
        audiences: user.audiences || [],
        roles: user.roles || [],
      });
      const option = document.createElement("option");
      option.value = user.user_id;
      const audiences = (user.audiences || []).join(", ");
      option.textContent = audiences
        ? `${user.display_name} (${user.user_id}) · ${audiences}`
        : `${user.display_name} (${user.user_id})`;
      authUser.appendChild(option);
    }
    if (session?.user_id && (!session.audiences || session.audiences.length === 0)) {
      const entry = chatUserDirectory.get(session.user_id);
      if (entry) {
        session = { ...session, audiences: entry.audiences, roles: entry.roles };
        saveSession();
      }
    }
    updateModeVisibility();
  } catch (error) {
    console.warn("could not load chat users", error);
  }
}

async function login() {
  const userId = authUser.value;
  const password = authPassword.value;
  if (!userId || !password) {
    authStatus.textContent = "Select user and enter password";
    return;
  }

  authLoginBtn.disabled = true;
  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, password }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    const directory = chatUserDirectory.get(payload.user_id) || {};
    session = {
      user_id: payload.user_id,
      session_id: payload.session_id,
      session_token: payload.session_token,
      audiences: payload.audiences || directory.audiences || [],
      roles: payload.roles || directory.roles || [],
    };
    saveSession();
    authPassword.value = "";
  } catch (error) {
    authStatus.textContent = `Login failed: ${error.message}`;
    authStatus.classList.add("muted");
  } finally {
    authLoginBtn.disabled = false;
  }
}

function logout() {
  session = null;
  saveSession();
}

function authHeaders() {
  if (!session) {
    return {};
  }
  return {
    Authorization: `Bearer ${session.session_token}`,
    "X-Session-Id": session.session_id,
  };
}

function appendMessage(role, content, chatMeta = null) {
  const wrap = document.createElement("div");
  wrap.className = `message ${role}`;
  wrap.innerHTML = `
    <div class="message-role">${role === "user" ? "You" : ASSISTANT_NAME}</div>
    <div class="message-body"></div>
  `;
  const body = wrap.querySelector(".message-body");
  if (role === "assistant") {
    const isRateLimited =
      Boolean(chatMeta?.retry_after_seconds) ||
      chatMeta?.routing?.intent_id === "llm.rate_limited";

    if (chatMeta?.skill_activities?.length) {
      const activityList = document.createElement("ul");
      activityList.className = "skill-activities";
      for (const line of chatMeta.skill_activities) {
        const item = document.createElement("li");
        item.textContent = line.replace(/\*\*/g, "");
        activityList.appendChild(item);
      }
      body.appendChild(activityList);
    }
    const answerDiv = document.createElement("div");
    answerDiv.className = isRateLimited ? "skill-answer rate-limit-copy" : "skill-answer";
    answerDiv.innerHTML = renderAssistantMarkdown(content);
    body.appendChild(answerDiv);
    if (isRateLimited) {
      body.appendChild(
        createRateLimitPanel({
          question: chatMeta.retry_question || "",
          retryAfterSeconds: Number(chatMeta.retry_after_seconds) || 30,
        })
      );
      wrap.classList.add("rate-limited");
    }
    if (chatMeta?.skill_confirmation) {
      body.appendChild(createSkillConfirmation(chatMeta.skill_confirmation, chatMeta));
    }
    if (chatMeta?.routing && !isRateLimited) {
      wrap.appendChild(createFeedbackBar(chatMeta));
    }
  } else {
    body.textContent = content;
  }
  thread.appendChild(wrap);
  thread.scrollTop = thread.scrollHeight;
}

function createRateLimitPanel({ question, retryAfterSeconds }) {
  const panel = document.createElement("div");
  panel.className = "rate-limit-panel";
  panel.setAttribute("role", "status");
  panel.setAttribute("aria-live", "polite");

  const echoed = question.trim() || "(same question)";
  const total = Math.max(1, Math.floor(retryAfterSeconds));

  panel.innerHTML = `
    <div class="rate-limit-banner">
      <span class="rate-limit-pulse" aria-hidden="true"></span>
      <div>
        <div class="rate-limit-title">Vendor under stress</div>
        <p class="rate-limit-sub muted">
          Google Gemini returned <span class="mono">429 RESOURCE_EXHAUSTED</span>.
          Capacity usually recovers in about half a minute.
        </p>
      </div>
    </div>
    <div class="rate-limit-question">
      <div class="rate-limit-question-label">Question to retry</div>
      <blockquote class="rate-limit-quote">${escapeHtml(echoed)}</blockquote>
    </div>
    <div class="rate-limit-actions">
      <button type="button" class="rate-limit-timer" disabled aria-label="Cooldowning until retry">
        <svg class="rate-limit-ring" viewBox="0 0 64 64" aria-hidden="true">
          <circle class="rate-limit-ring-track" cx="32" cy="32" r="26"></circle>
          <circle class="rate-limit-ring-progress" cx="32" cy="32" r="26"></circle>
        </svg>
        <span class="rate-limit-count">${total}</span>
      </button>
      <div class="rate-limit-hint muted">
        Countdown arms the retry control. Stay on this turn — your question is preserved.
      </div>
    </div>
  `;

  const timerBtn = panel.querySelector(".rate-limit-timer");
  const countEl = panel.querySelector(".rate-limit-count");
  const progress = panel.querySelector(".rate-limit-ring-progress");
  const circumference = 2 * Math.PI * 26;
  progress.style.strokeDasharray = String(circumference);
  progress.style.strokeDashoffset = "0";

  let remaining = total;
  const startedAt = Date.now();

  function paint(secondsLeft) {
    countEl.textContent = String(secondsLeft);
    const ratio = secondsLeft / total;
    progress.style.strokeDashoffset = String(circumference * (1 - ratio));
  }

  paint(remaining);

  const tick = window.setInterval(() => {
    const elapsed = Math.floor((Date.now() - startedAt) / 1000);
    remaining = Math.max(0, total - elapsed);
    paint(remaining);
    if (remaining <= 0) {
      window.clearInterval(tick);
      timerBtn.disabled = false;
      timerBtn.classList.add("ready");
      timerBtn.setAttribute("aria-label", "Retry the same question");
      countEl.textContent = "Retry";
      progress.style.strokeDashoffset = String(circumference);
      panel.classList.add("ready");
    }
  }, 250);

  timerBtn.addEventListener("click", () => {
    if (timerBtn.disabled || !question.trim()) {
      return;
    }
    timerBtn.disabled = true;
    panel.classList.add("resolved");
    sendMessage(question.trim());
  });

  return panel;
}

function createSkillConfirmation(confirmation, chatMeta) {
  const card = confirmation.card || {};
  const skill = confirmation.skill || "create_payment";
  const isSubmit = skill === "submit_payment";
  const isApprove = skill === "approve_payment";
  const isCancel = skill === "cancel_payment";
  const panel = document.createElement("div");
  panel.className = "skill-confirm";
  panel.dataset.pendingId = confirmation.pending_id;
  panel.dataset.skill = skill;

  const intermediaryText = (card.intermediaries || []).length
    ? (card.intermediaries || []).join("; ")
    : "None";

  const paymentRow = card.payment_id
    ? `<dt>Payment</dt><dd class="mono">${escapeHtml(card.payment_id)}</dd>
       <dt>Payment status</dt><dd>${escapeHtml(card.payment_status || "DRAFT")}</dd>`
    : "";

  const title = isCancel
    ? "Confirm payment cancel"
    : isApprove
      ? "Confirm payment approve"
      : isSubmit
        ? "Confirm payment submit"
        : "Confirm payment create";

  panel.innerHTML = `
    <div class="skill-confirm-title">${title}</div>
    <dl class="skill-confirm-grid">
      ${paymentRow}
      <dt>Instruction</dt><dd class="mono">${escapeHtml(card.instruction_id || "—")}</dd>
      <dt>Amount</dt><dd><strong>${escapeHtml(String(card.currency || ""))} ${escapeHtml(formatNumber(card.amount))}</strong></dd>
      <dt>Value date</dt><dd>${escapeHtml(card.value_date || "—")}</dd>
      <dt>Owning LOB</dt><dd>${escapeHtml(card.owning_lob || "—")}</dd>
      <dt>Debtor</dt><dd>${escapeHtml(card.debtor_name || "—")}</dd>
      <dt>Debtor account</dt><dd class="mono">${escapeHtml(card.debtor_account || "—")}</dd>
      <dt>Creditor</dt><dd>${escapeHtml(card.creditor_name || "—")}</dd>
      <dt>Creditor account</dt><dd class="mono">${escapeHtml(card.creditor_account || "—")}</dd>
      <dt>Intermediaries</dt><dd>${escapeHtml(intermediaryText)}</dd>
    </dl>
    <div class="skill-confirm-actions">
      <button type="button" class="btn btn-go">Go</button>
      <button type="button" class="btn btn-nogo">No Go</button>
      <span class="skill-confirm-status muted"></span>
    </div>
  `;

  const goBtn = panel.querySelector(".btn-go");
  const noGoBtn = panel.querySelector(".btn-nogo");
  const status = panel.querySelector(".skill-confirm-status");
  const confirmPath = isCancel
    ? "/api/chat/skills/cancel-payment/confirm"
    : isApprove
      ? "/api/chat/skills/approve-payment/confirm"
      : isSubmit
        ? "/api/chat/skills/submit-payment/confirm"
        : "/api/chat/skills/create-payment/confirm";

  async function decide(decision) {
    goBtn.disabled = true;
    noGoBtn.disabled = true;
    status.textContent = decision === "go"
      ? (isApprove ? "Approving…" : isSubmit ? "Submitting…" : "Creating…")
      : "Cancelling…";
    try {
      const response = await fetch(confirmPath, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders(),
        },
        body: JSON.stringify({
          pending_id: confirmation.pending_id,
          decision,
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || `HTTP ${response.status}`);
      }
      panel.classList.add("resolved");
      status.textContent = decision === "go" ? "Go" : "No Go";
      appendMessage("assistant", payload.answer, {
        mode: chatMeta?.mode || "payments",
        routing: payload.routing,
        skill_activities: payload.skill_activities,
      });
      history.push({ role: "assistant", content: payload.answer });
      if (history.length > 40) {
        history = history.slice(-40);
      }
      renderMeta(payload);
    } catch (error) {
      goBtn.disabled = false;
      noGoBtn.disabled = false;
      status.textContent = `Failed: ${error.message}`;
    }
  }

  goBtn.addEventListener("click", () => decide("go"));
  noGoBtn.addEventListener("click", () => decide("no_go"));
  return panel;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatNumber(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "—";
  return num.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function createFeedbackBar(chatMeta) {
  const bar = document.createElement("div");
  bar.className = "message-feedback";
  bar.setAttribute("role", "group");
  bar.setAttribute("aria-label", "Rate this answer");

  const label = document.createElement("span");
  label.className = "feedback-label muted";
  label.textContent = "Helpful?";

  const upBtn = document.createElement("button");
  upBtn.type = "button";
  upBtn.className = "feedback-btn feedback-up";
  upBtn.setAttribute("aria-label", "Thumbs up");
  upBtn.textContent = "👍";

  const downBtn = document.createElement("button");
  downBtn.type = "button";
  downBtn.className = "feedback-btn feedback-down";
  downBtn.setAttribute("aria-label", "Thumbs down");
  downBtn.textContent = "👎";

  const status = document.createElement("span");
  status.className = "feedback-status muted";

  async function submitFeedback(rating) {
    if (bar.dataset.submitted) {
      return;
    }
    upBtn.disabled = true;
    downBtn.disabled = true;
    status.textContent = "Saving…";

    const routing = chatMeta.routing;
    try {
      const response = await fetch("/api/chat/feedback", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders(),
        },
        body: JSON.stringify({
          rating,
          mode: chatMeta.mode,
          path: routing.path,
          cypher_provenance: routing.cypher_provenance,
          answer_synthesis: routing.answer_synthesis,
          retrieval_strategy: routing.retrieval_strategy || null,
          intent_id: routing.intent_id || null,
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || `HTTP ${response.status}`);
      }
      bar.dataset.submitted = rating;
      upBtn.classList.toggle("selected", rating === "up");
      downBtn.classList.toggle("selected", rating === "down");
      status.textContent = "Thanks for your feedback";
    } catch (error) {
      upBtn.disabled = false;
      downBtn.disabled = false;
      status.textContent = `Could not save feedback: ${error.message}`;
    }
  }

  upBtn.addEventListener("click", () => submitFeedback("up"));
  downBtn.addEventListener("click", () => submitFeedback("down"));

  bar.append(label, upBtn, downBtn, status);
  return bar;
}

function shortId(value) {
  if (!value) return "—";
  const parts = String(value).split("-");
  return parts.length > 1 ? parts[parts.length - 1] : value;
}

function renderMeta(data) {
  metaEmpty.classList.add("hidden");
  metaContent.classList.remove("hidden");

  metaTiming.textContent = `Retrieval ${data.retrieval_ms ?? "—"} ms · Generation ${data.generation_ms ?? "—"} ms`;
  metaCypher.textContent = data.cypher || "(no Cypher generated)";

  const routing = data.routing;
  if (routing) {
    metaRouting.textContent = routing.label || "Unknown path";
    const detailParts = [
      routing.retrieval_strategy && `strategy=${routing.retrieval_strategy}`,
      routing.path && `path=${routing.path}`,
      routing.cypher_provenance && `cypher=${routing.cypher_provenance}`,
      routing.answer_synthesis && `synthesis=${routing.answer_synthesis}`,
      routing.intent_id && `intent=${routing.intent_id}`,
    ].filter(Boolean);
    metaRoutingDetail.textContent = detailParts.join(" · ");
  } else {
    metaRouting.textContent = "(routing metadata unavailable)";
    metaRoutingDetail.textContent = "";
  }

  metaSources.innerHTML = "";
  if (!data.sources || data.sources.length === 0) {
    metaSources.innerHTML = '<p class="muted">No event sources merged.</p>';
    return;
  }

  data.sources.forEach((source, index) => {
    const card = document.createElement("article");
    card.className = "source-card";
    card.innerHTML = `
      <div class="source-header">
        <span class="source-index">#${index + 1}</span>
        <span class="source-score mono">${source.score.toFixed(4)}</span>
      </div>
      <p class="source-tags mono">${(source.sources || []).join(" · ")}</p>
      <p class="source-ids mono">event ${shortId(source.event_id)} · instr ${shortId(source.instruction_id)}</p>
      <p class="source-summary">${source.summary || "—"}</p>
    `;
    metaSources.appendChild(card);
  });
}

function getSelectedMode() {
  const checked = document.querySelector('input[name="mode"]:checked');
  return checked ? checked.value : "events";
}

async function sendMessage(text) {
  if (!session) {
    authStatus.textContent = "Sign in required before chatting";
    authStatus.classList.add("muted");
    return;
  }

  const mode = getSelectedMode();
  sendBtn.disabled = true;
  sendBtn.textContent = "Thinking…";

  const modeLabel = {
    events: "🔍 Events",
    instructions: "📋 Instructions",
    payments: "💳 Payments",
    policies: "📜 Policies",
    all: "🔀 All entities",
  }[mode] || mode;
  appendMessage("user", `[${modeLabel}] ${text}`);
  history.push({ role: "user", content: text });

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify({ message: text, history: history.slice(0, -1), mode }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    appendMessage("assistant", payload.answer, {
      mode,
      routing: payload.routing,
      skill_activities: payload.skill_activities,
      skill_confirmation: payload.skill_confirmation,
      retry_after_seconds: payload.retry_after_seconds,
      retry_question: text,
    });
    history.push({ role: "assistant", content: payload.answer });
    if (history.length > 40) {
      history = history.slice(-40);
    }
    renderMeta(payload);
  } catch (error) {
    const detail = String(error.message || error);
    const looksRateLimited =
      /RESOURCE_EXHAUSTED/i.test(detail) ||
      /\b429\b/.test(detail) ||
      /rate.?limit/i.test(detail);
    if (looksRateLimited) {
      appendMessage(
        "assistant",
        "Google Gemini (our answer model) is temporarily under stress (HTTP 429 · Resource Exhausted). Vendor capacity recovered slowly — please wait about 30 seconds, then retry the same question.",
        {
          mode,
          routing: {
            path: "full_rag",
            cypher_provenance: "none",
            answer_synthesis: "formatter",
            label: "Gemini rate limited",
            intent_id: "llm.rate_limited",
            retrieval_strategy: "graph",
          },
          retry_after_seconds: 30,
          retry_question: text,
        }
      );
    } else {
      appendMessage("assistant", `${ASSISTANT_NAME} hit an error: ${error.message}`);
    }
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = "Send";
    input.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text || sendBtn.disabled || !session) {
    if (!session) {
      authStatus.textContent = "Sign in required before chatting";
      authStatus.classList.add("muted");
    }
    return;
  }
  input.value = "";
  sendMessage(text);
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

clearBtn.addEventListener("click", () => {
  history = [];
  thread.innerHTML = "";
  appendMessage(
    "assistant",
    "Chat cleared. Ask PolicyPilot a new question about security events, instructions, or payments."
  );
  metaEmpty.classList.remove("hidden");
  metaContent.classList.add("hidden");
  input.focus();
});

authLoginBtn.addEventListener("click", login);
authLogoutBtn.addEventListener("click", logout);
authPassword.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    login();
  }
});

loadSession();
loadChatUsers();
input.focus();

const integrityBanner = document.getElementById("index-integrity-banner");

async function refreshIndexIntegrityBanner() {
  if (!integrityBanner) return;
  try {
    const response = await fetch("/api/index-integrity");
    if (!response.ok) {
      integrityBanner.classList.add("hidden");
      return;
    }
    const data = await response.json();
    if (data.show_banner && data.banner_message) {
      integrityBanner.textContent = data.banner_message;
      integrityBanner.classList.remove("hidden");
    } else {
      integrityBanner.classList.add("hidden");
      integrityBanner.textContent = "";
    }
  } catch (_error) {
    integrityBanner.classList.add("hidden");
  }
}

void refreshIndexIntegrityBanner();
setInterval(() => void refreshIndexIntegrityBanner(), 15000);
