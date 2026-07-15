const componentsGrid = document.getElementById("components-grid");
const modeHint = document.getElementById("mode-hint");
const searchForm = document.getElementById("search-form");
const searchBtn = document.getElementById("search-btn");
const queryInput = document.getElementById("query-input");
const limitInput = document.getElementById("limit-input");
const neo4jActionWrap = document.getElementById("neo4j-action-wrap");
const neo4jActionInput = document.getElementById("neo4j-action-input");
const resultsTitle = document.getElementById("results-title");
const resultsMeta = document.getElementById("results-meta");
const resultsEmpty = document.getElementById("results-empty");
const resultsList = document.getElementById("results-list");
const resultsDetail = document.getElementById("results-detail");
const clearResultsBtn = document.getElementById("clear-results-btn");
const modeTabs = document.querySelectorAll(".mode-tab");

const MODE_HINTS = {
  vector: "Semantic search using Vertex dense embeddings stored in Neo4j.",
  neo4j: "Cypher text search over SecurityEvent nodes in the Neo4j graph.",
};

let mode = "vector";
let selectedCard = null;
let componentsTimer = null;

async function apiFetch(url, options = {}) {
  return AdminAuth.adminFetch(url, options);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function setMode(nextMode) {
  mode = nextMode;
  modeTabs.forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.mode === mode);
  });
  modeHint.textContent = MODE_HINTS[mode] || "";
  const neo4jMode = mode === "neo4j";
  neo4jActionWrap.classList.toggle("hidden", !neo4jMode);
  neo4jActionWrap.setAttribute("aria-hidden", neo4jMode ? "false" : "true");
  resultsTitle.textContent =
    mode === "neo4j" ? "Neo4j graph matches" : `Vector ${mode} matches`;
}

function clearResults() {
  resultsList.innerHTML = "";
  resultsList.classList.add("hidden");
  resultsDetail.classList.add("hidden");
  resultsDetail.textContent = "";
  resultsMeta.textContent = "";
  resultsEmpty.classList.remove("hidden", "error");
  resultsEmpty.textContent = "Run a search to query indexed security events.";
  clearResultsBtn.classList.add("hidden");
  selectedCard = null;
}

const COMPONENT_LABELS = {
  kafka: "Kafka",
  vertex_embeddings: "Vertex embeddings",
  multimodal_vector: "Neo4j · Vector",
  neo4j: "Neo4j",
};

function componentDetail(key, component) {
  if (key === "kafka") {
    if (component.status === "disabled") {
      return "Consumer disabled";
    }
    return [
      component.topic,
      component.consumer === "running" ? "consumer running" : null,
      component.brokers != null ? `${component.brokers} broker(s)` : null,
    ]
      .filter(Boolean)
      .join(" · ");
  }
  if (key === "vertex_embeddings") {
    return [
      component.model,
      component.embeddings === "ready" ? `dim ${component.dimension}` : "not warmed up",
      component.project,
    ]
      .filter(Boolean)
      .join(" · ");
  }
  if (key === "multimodal_vector") {
    const docs =
      component.documents_count != null ? `${component.documents_count} document(s)` : null;
    const index = component.vector_index || component.store;
    return [index, docs].filter(Boolean).join(" · ");
  }
  if (key === "neo4j") {
    const nodes =
      component.total_nodes != null ? `${component.total_nodes} node(s)` : null;
    return [component.uri, nodes].filter(Boolean).join(" · ");
  }
  return component.detail || "";
}

function renderComponents(components) {
  componentsGrid.innerHTML = "";
  for (const key of Object.keys(COMPONENT_LABELS)) {
    const component = components[key] || { ok: false, status: "down" };
    const card = document.createElement("article");
    card.className = `component-card status-${component.status || (component.ok ? "up" : "down")}`;
    card.innerHTML = `
      <div class="component-head">
        <span class="component-name">${escapeHtml(COMPONENT_LABELS[key])}</span>
        <span class="component-pill ${escapeHtml(component.status || "down")}">${escapeHtml(component.status || "down")}</span>
      </div>
      <p class="component-detail">${escapeHtml(componentDetail(key, component) || component.detail || "—")}</p>
    `;
    if (!component.ok && component.detail) {
      card.title = component.detail;
    }
    componentsGrid.appendChild(card);
  }
}

async function refreshComponents() {
  if (!AdminAuth.loadSession()) {
    componentsGrid.innerHTML = '<div class="component-card status-down">Admin sign-in required</div>';
    renderKafkaConsumers([], "Sign in to load consumer offsets.");
    return;
  }
  try {
    const response = await apiFetch("/api/stats");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    renderComponents(data.components || {});
    const groups =
      data.consumer_groups ||
      data.integrity?.consumer_groups ||
      [];
    const totalLag =
      data.integrity?.kafka_lag_total ??
      groups.reduce((n, g) => n + (g.lag_total || 0), 0);
    renderKafkaConsumers(
      groups,
      `total lag=${totalLag} · ${groups.length} consumer group(s)`,
    );
  } catch (error) {
    componentsGrid.innerHTML = `<div class="component-card status-down">Component status unavailable: ${escapeHtml(error.message)}</div>`;
    renderKafkaConsumers([], `Consumer metadata unavailable: ${error.message}`);
  }
}

const kafkaConsumersSummary = document.getElementById("kafka-consumers-summary");
const kafkaConsumersBody = document.getElementById("kafka-consumers-body");
const kafkaConsumersRefreshBtn = document.getElementById("kafka-consumers-refresh-btn");

function renderKafkaConsumers(groups, summaryText) {
  if (kafkaConsumersSummary) {
    kafkaConsumersSummary.textContent = summaryText || "";
  }
  if (!kafkaConsumersBody) {
    return;
  }
  if (!groups || !groups.length) {
    kafkaConsumersBody.innerHTML = "";
    return;
  }
  const rows = [];
  for (const g of groups) {
    const partitions = g.partitions || [];
    if (!partitions.length) {
      rows.push(`<tr>
        <td>${escapeHtml(g.name)}</td>
        <td>${escapeHtml(g.topic)}</td>
        <td>${escapeHtml(g.consumer_group)}</td>
        <td>—</td>
        <td>—</td>
        <td>—</td>
        <td>—</td>
        <td>${g.lag_total ?? 0}</td>
        <td>${escapeHtml(g.status)}${g.pause_reason ? ` (${escapeHtml(g.pause_reason)})` : ""}</td>
      </tr>`);
      continue;
    }
    for (const p of partitions) {
      rows.push(`<tr>
        <td>${escapeHtml(g.name)}</td>
        <td>${escapeHtml(p.topic || g.topic)}</td>
        <td>${escapeHtml(g.consumer_group)}</td>
        <td>${p.partition ?? "—"}</td>
        <td>${p.committed_offset ?? "—"}</td>
        <td>${p.position ?? "—"}</td>
        <td>${p.latest_offset ?? "—"}</td>
        <td>${p.lag ?? 0}</td>
        <td>${escapeHtml(g.status)}${g.pause_reason ? ` (${escapeHtml(g.pause_reason)})` : ""}</td>
      </tr>`);
    }
  }
  kafkaConsumersBody.innerHTML = rows.join("");
}

if (kafkaConsumersRefreshBtn) {
  kafkaConsumersRefreshBtn.addEventListener("click", () => void refreshComponents());
}

async function refreshStats() {
  await refreshComponents();
}

function securityEventSummary(result) {
  const event = result.security_event || result.payload?.security_event || result.event || result;
  const ctx = event.event || {};
  return {
    eventId: result.event_id || event.event_id,
    message: event.message || result.search_text || "—",
    action: ctx.action || event.action || "—",
    severity: event.severity || "—",
    outcome: ctx.outcome || event.outcome || "—",
    score: result.score,
  };
}

function showDetail(payload) {
  resultsDetail.classList.remove("hidden");
  resultsDetail.textContent = JSON.stringify(payload, null, 2);
}

function renderVectorResults(results) {
  resultsList.innerHTML = "";
  results.forEach((result) => {
    const summary = securityEventSummary(result);
    const card = document.createElement("article");
    card.className = "result-card";
    const badgeClass = summary.severity === "ALERT" ? "badge badge-ALERT" : "badge";
    card.innerHTML = `
      <div class="result-head">
        <span class="${badgeClass}">${escapeHtml(summary.severity)}</span>
        <span class="mono score">score ${summary.score?.toFixed?.(4) ?? "—"}</span>
      </div>
      <p class="result-message">${escapeHtml(summary.message)}</p>
      <div class="result-meta mono">
        <span>${escapeHtml(summary.action)}</span>
        <span>${escapeHtml(summary.outcome)}</span>
        <span>${escapeHtml(summary.eventId || "—")}</span>
      </div>
    `;
    card.addEventListener("click", () => {
      if (selectedCard) {
        selectedCard.classList.remove("selected");
      }
      card.classList.add("selected");
      selectedCard = card;
      showDetail(result);
    });
    resultsList.appendChild(card);
  });
}

function renderNeo4jResults(events) {
  resultsList.innerHTML = "";
  events.forEach((event) => {
    const card = document.createElement("article");
    card.className = "result-card";
    const badgeClass = event.severity === "ALERT" ? "badge badge-ALERT" : "badge";
    card.innerHTML = `
      <div class="result-head">
        <span class="${badgeClass}">${escapeHtml(event.severity || "—")}</span>
        <span class="mono">${escapeHtml(event.action || "—")}</span>
      </div>
      <p class="result-message">${escapeHtml(event.message || "—")}</p>
      <div class="result-meta mono">
        <span>${escapeHtml(event.outcome || "—")}</span>
        <span>${escapeHtml(event.event_id || "—")}</span>
      </div>
    `;
    card.addEventListener("click", async () => {
      if (!event.event_id) {
        showDetail(event);
        return;
      }
      if (selectedCard) {
        selectedCard.classList.remove("selected");
      }
      card.classList.add("selected");
      selectedCard = card;
      try {
        const response = await apiFetch(`/api/graph/events/${encodeURIComponent(event.event_id)}`);
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail || `HTTP ${response.status}`);
        }
        showDetail(payload);
      } catch (error) {
        showDetail({ error: error.message, event });
      }
    });
    resultsList.appendChild(card);
  });
}

modeTabs.forEach((tab) => {
  tab.addEventListener("click", () => setMode(tab.dataset.mode));
});

clearResultsBtn.addEventListener("click", clearResults);

searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = queryInput.value.trim();
  const limit = Number.parseInt(limitInput.value, 10) || 10;
  if (!query) {
    return;
  }

  searchBtn.disabled = true;
  resultsEmpty.classList.remove("error");
  resultsEmpty.textContent = "Searching…";
  resultsEmpty.classList.remove("hidden");
  resultsList.classList.add("hidden");
  resultsDetail.classList.add("hidden");
  resultsMeta.textContent = "";

  try {
    let response;
    if (mode === "neo4j") {
      const params = new URLSearchParams({ q: query, limit: String(limit) });
      const action = neo4jActionInput.value.trim();
      if (action) {
        params.set("action", action);
      }
      response = await apiFetch(`/api/graph/events?${params.toString()}`);
    } else {
      response = await apiFetch(`/api/search/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, limit }),
      });
    }

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(
        typeof payload.detail === "string"
          ? payload.detail
          : JSON.stringify(payload.detail || payload),
      );
    }

    const results = payload.results || payload.events || [];
    if (results.length === 0) {
      resultsEmpty.classList.remove("hidden");
      resultsEmpty.textContent =
        "No matches. Generate events via the test harness, then wait for Kafka ETL to index them.";
      resultsList.classList.add("hidden");
    } else {
      resultsEmpty.classList.add("hidden");
      resultsList.classList.remove("hidden");
      if (mode === "neo4j") {
        renderNeo4jResults(results);
        resultsMeta.textContent = `${payload.count || 0} graph match(es)`;
      } else {
        renderVectorResults(results);
        resultsMeta.textContent = `${payload.count || 0} hit(s) · ${payload.mode}`;
      }
      clearResultsBtn.classList.remove("hidden");
    }
  } catch (error) {
    resultsList.classList.add("hidden");
    resultsEmpty.classList.remove("hidden");
    resultsEmpty.classList.add("error");
    resultsEmpty.textContent = `Search failed: ${error.message}`;
  } finally {
    searchBtn.disabled = false;
  }
});

setMode("vector");

function startComponentsPolling() {
  if (componentsTimer) {
    clearInterval(componentsTimer);
  }
  void refreshComponents();
  void refreshChunkStats();
  void refreshSearchProfiles();
  void refreshDlq();
  componentsTimer = setInterval(() => {
    void refreshComponents();
    void refreshChunkStats();
    void refreshSearchProfiles();
    void refreshDlq();
  }, 20000);
}

const dlqSummary = document.getElementById("dlq-summary");
const dlqBody = document.getElementById("dlq-body");
const dlqRefreshBtn = document.getElementById("dlq-refresh-btn");
const dlqRetryBtn = document.getElementById("dlq-retry-btn");
const dlqResumeBtn = document.getElementById("dlq-resume-btn");

async function refreshDlq() {
  if (!AdminAuth.loadSession()) {
    if (dlqSummary) dlqSummary.textContent = "Sign in to load DLQ stats.";
    if (dlqBody) dlqBody.innerHTML = "";
    if (dlqRetryBtn) dlqRetryBtn.disabled = true;
    return;
  }
  try {
    const [statsResp, entriesResp] = await Promise.all([
      apiFetch("/api/dlq/stats"),
      apiFetch("/api/dlq/entries?limit=50&active_only=true"),
    ]);
    const stats = await statsResp.json();
    const entries = await entriesResp.json();
    const by = stats.by_status || {};
    const depth = Number(stats.depth || 0);
    const paused = stats.any_paused
      ? ` · consumers paused: ${JSON.stringify(stats.consumers || {})}`
      : "";
    if (dlqSummary) {
      dlqSummary.textContent =
        `depth=${depth} · pending=${by.pending || 0} · ` +
        `processing=${by.processing || 0} · exhausted=${by.exhausted || 0} · ` +
        `processed=${by.processed || 0} · poison=${by.poison || 0}` +
        paused;
    }
    if (dlqRetryBtn) {
      dlqRetryBtn.disabled = depth <= 0;
    }
    if (dlqBody) {
      const rows = entries.entries || [];
      if (!rows.length) {
        dlqBody.innerHTML =
          `<tr><td colspan="6" class="muted">No unresolved DLQ entries` +
          `${by.processed ? ` (${by.processed} processed)` : ""}.</td></tr>`;
      } else {
        dlqBody.innerHTML = rows
          .map((e) => {
            const k = e.kafka || {};
            const err = escapeHtml(e.last_error || e.error_message || "");
            return `<tr>
              <td>${escapeHtml(e.status)}</td>
              <td>${escapeHtml(e.pipeline_kind)}</td>
              <td>${escapeHtml(e.event_id || e.entity_id || "—")}</td>
              <td>${e.attempts ?? 0}/${e.max_attempts ?? "?"}</td>
              <td title="${err}">${err.slice(0, 80)}</td>
              <td>${escapeHtml(k.topic || "")}:${k.partition ?? ""}:${k.offset ?? ""}</td>
            </tr>`;
          })
          .join("");
      }
    }
  } catch (error) {
    if (dlqSummary) dlqSummary.textContent = `DLQ load failed: ${error.message}`;
    if (dlqRetryBtn) dlqRetryBtn.disabled = true;
  }
}

if (dlqRefreshBtn) {
  dlqRefreshBtn.addEventListener("click", () => void refreshDlq());
}
if (dlqRetryBtn) {
  dlqRetryBtn.addEventListener("click", async () => {
    if (!AdminAuth.loadSession() || dlqRetryBtn.disabled) return;
    dlqRetryBtn.disabled = true;
    try {
      await apiFetch("/api/dlq/retry-now", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "ops_ui_retry_now" }),
      });
    } finally {
      await refreshDlq();
    }
  });
}
if (dlqResumeBtn) {
  dlqResumeBtn.addEventListener("click", async () => {
    if (!AdminAuth.loadSession()) return;
    await apiFetch("/api/dlq/resume-consumers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    await refreshDlq();
  });
}

// ── Indexed text size monitor ─────────────────────────────────────────────

const chunkStatsEmpty = document.getElementById("chunk-stats-empty");
const chunkStatsContent = document.getElementById("chunk-stats-content");
const chunkStatsSummary = document.getElementById("chunk-stats-summary");
const chunkStatsBody = document.getElementById("chunk-stats-body");
const chunkStatsRefreshBtn = document.getElementById("chunk-stats-refresh-btn");
const chunkEmbedLimit = document.getElementById("chunk-embed-limit");

function formatNumber(value) {
  return Number(value ?? 0).toLocaleString();
}

function renderChunkStats(data) {
  const summary = data.summary || {};
  const chars = summary.char_count || {};
  const words = summary.word_count || {};
  const tokens = summary.estimated_tokens || {};
  const maxTokens = tokens.max || 0;
  const contextLimit = data.embedding_context_tokens || 32768;
  const headroomPct = contextLimit
    ? Math.round((maxTokens / contextLimit) * 1000) / 10
    : 0;

  chunkStatsSummary.innerHTML = `
    <article class="chunk-stat-card">
      <span class="chunk-stat-label">Points indexed</span>
      <strong class="chunk-stat-value">${formatNumber(data.points_count)}</strong>
      <span class="chunk-stat-detail mono">${escapeHtml(data.collection || "—")}</span>
    </article>
    <article class="chunk-stat-card">
      <span class="chunk-stat-label">Largest text</span>
      <strong class="chunk-stat-value">${formatNumber(chars.max)} chars</strong>
      <span class="chunk-stat-detail">~${formatNumber(tokens.max)} tokens · ${headroomPct}% of ${formatNumber(contextLimit)} limit</span>
    </article>
    <article class="chunk-stat-card">
      <span class="chunk-stat-label">Average text</span>
      <strong class="chunk-stat-value">${formatNumber(chars.avg)} chars</strong>
      <span class="chunk-stat-detail">${formatNumber(words.avg)} words avg · median ${formatNumber(chars.median)} chars</span>
    </article>
    <article class="chunk-stat-card">
      <span class="chunk-stat-label">Indexing model</span>
      <strong class="chunk-stat-value">No chunking</strong>
      <span class="chunk-stat-detail">1 point = 1 record · embedded field = search_text subset</span>
    </article>
  `;

  if (chunkEmbedLimit && contextLimit) {
    chunkEmbedLimit.textContent = `${Math.round(contextLimit / 1000)}K`;
  }

  chunkStatsBody.innerHTML = "";
  (data.top_chunks || []).forEach((row) => {
    const tr = document.createElement("tr");
    const recordId =
      row.event_id || row.payment_id || row.instruction_id || row.record_id || row.point_id;
    tr.innerHTML = `
      <td class="mono">${row.rank ?? "—"}</td>
      <td><span class="chunk-source-pill">${escapeHtml(row.source || "unknown")}</span></td>
      <td class="mono chunk-record-id">${escapeHtml(recordId || "—")}</td>
      <td class="mono">${formatNumber(row.char_count)}</td>
      <td class="mono">${formatNumber(row.word_count)}</td>
      <td class="mono">${formatNumber(row.estimated_tokens)}</td>
      <td class="chunk-preview" title="${escapeHtml(row.preview || "")}">${escapeHtml(row.preview || "—")}</td>
    `;
    chunkStatsBody.appendChild(tr);
  });

  chunkStatsEmpty.classList.add("hidden");
  chunkStatsContent.classList.remove("hidden");
}

async function refreshChunkStats() {
  if (!AdminAuth.loadSession()) {
    chunkStatsContent.classList.add("hidden");
    chunkStatsEmpty.classList.remove("hidden");
    chunkStatsEmpty.textContent = "Sign in to load chunk size stats from the vector store.";
    return;
  }

  chunkStatsRefreshBtn.disabled = true;
  try {
    const response = await apiFetch("/api/vector/chunk-stats?limit=10");
    const data = await response.json();
    if (!response.ok) {
      throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${response.status}`);
    }
    if (!data.points_count) {
      chunkStatsContent.classList.add("hidden");
      chunkStatsEmpty.classList.remove("hidden");
      chunkStatsEmpty.textContent = "No indexed points yet — generate events via the test harness.";
      return;
    }
    renderChunkStats(data);
  } catch (error) {
    chunkStatsContent.classList.add("hidden");
    chunkStatsEmpty.classList.remove("hidden");
    chunkStatsEmpty.textContent = `Chunk stats unavailable: ${error.message}`;
  } finally {
    chunkStatsRefreshBtn.disabled = false;
  }
}

if (chunkStatsRefreshBtn) {
  chunkStatsRefreshBtn.addEventListener("click", () => {
    void refreshChunkStats();
  });
}

// ── Search text profiles ───────────────────────────────────────────────────

const searchProfilesEmpty = document.getElementById("search-profiles-empty");
const searchProfilesContent = document.getElementById("search-profiles-content");
const searchProfilesList = document.getElementById("search-profiles-list");
const searchProfilesRefreshBtn = document.getElementById("search-profiles-refresh-btn");

function formatProfileField(item) {
  if (item.literal != null) {
    return `literal: "${item.literal}"`;
  }
  const path = item.path || "—";
  return item.transform ? `${path} (${item.transform})` : path;
}

function renderSearchProfiles(data) {
  searchProfilesList.innerHTML = "";
  (data.profiles || []).forEach((profile, index) => {
    const details = document.createElement("details");
    details.className = "search-profile-card";
    if (index === 0) {
      details.open = true;
    }

    const included = (profile.includes || [])
      .map((item) => `<li>${escapeHtml(formatProfileField(item))}</li>`)
      .join("");
    const excluded = (profile.excludes || [])
      .map((item) => `<li>${escapeHtml(item)}</li>`)
      .join("");

    details.innerHTML = `
      <summary>
        <span class="search-profile-meta">
          <span>${escapeHtml(profile.entity || "unknown")}</span>
          <span class="chunk-source-pill">${escapeHtml(profile.payload_source || profile.entity || "—")}</span>
          <span class="chunk-source-pill">${profile.wired ? "wired" : "documented"}</span>
        </span>
      </summary>
      <div class="search-profile-body">
        <p class="search-profile-desc">${escapeHtml(profile.description || "—")}</p>
        <p class="search-profile-desc mono">context_root: ${escapeHtml(profile.context_root || "—")}</p>
        <div class="search-profile-columns">
          <div>
            <h3>In search_text (${(profile.includes || []).length})</h3>
            <ul class="search-profile-fields">${included || "<li>—</li>"}</ul>
          </div>
          <div>
            <h3>Payload only (${(profile.excludes || []).length})</h3>
            <ul class="search-profile-fields">${excluded || "<li>—</li>"}</ul>
          </div>
        </div>
      </div>
    `;
    searchProfilesList.appendChild(details);
  });

  searchProfilesEmpty.classList.add("hidden");
  searchProfilesContent.classList.remove("hidden");
}

async function refreshSearchProfiles() {
  if (!searchProfilesList) {
    return;
  }
  if (!AdminAuth.loadSession()) {
    searchProfilesContent.classList.add("hidden");
    searchProfilesEmpty.classList.remove("hidden");
    searchProfilesEmpty.textContent = "Sign in to load search profile definitions.";
    return;
  }

  if (searchProfilesRefreshBtn) {
    searchProfilesRefreshBtn.disabled = true;
  }
  try {
    const response = await apiFetch("/api/search-profiles");
    const data = await response.json();
    if (!response.ok) {
      throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${response.status}`);
    }
    renderSearchProfiles(data);
  } catch (error) {
    searchProfilesContent.classList.add("hidden");
    searchProfilesEmpty.classList.remove("hidden");
    searchProfilesEmpty.textContent = `Search profiles unavailable: ${error.message}`;
  } finally {
    if (searchProfilesRefreshBtn) {
      searchProfilesRefreshBtn.disabled = false;
    }
  }
}

if (searchProfilesRefreshBtn) {
  searchProfilesRefreshBtn.addEventListener("click", () => {
    void refreshSearchProfiles();
  });
}

AdminAuth.bindAdminAuthPanel({
  statusEl: document.getElementById("auth-status"),
  userEl: document.getElementById("auth-user"),
  passwordEl: document.getElementById("auth-password"),
  loginBtn: document.getElementById("auth-login-btn"),
  logoutBtn: document.getElementById("auth-logout-btn"),
  onAuthenticated: () => {
    startComponentsPolling();
  },
});

// ── Question → Intent pane ────────────────────────────────────────────────

const intentForm = document.getElementById("intent-form");
const intentModeSelect = document.getElementById("intent-mode-select");
const intentQuestionInput = document.getElementById("intent-question-input");
const intentExtractBtn = document.getElementById("intent-extract-btn");
const intentExtractStatus = document.getElementById("intent-extract-status");
const intentOutputWrap = document.getElementById("intent-output-wrap");
const intentOutput = document.getElementById("intent-output");
const intentOutputMeta = document.getElementById("intent-output-meta");
const intentCopyBtn = document.getElementById("intent-copy-btn");
const intentClearBtn = document.getElementById("intent-clear-btn");

let intentBusy = false;

function setIntentBusy(next) {
  intentBusy = next;
  intentExtractBtn.disabled = next;
}

function clearIntentOutput() {
  intentOutputWrap.classList.add("hidden");
  intentOutput.textContent = "";
  intentOutputMeta.textContent = "";
  intentExtractStatus.textContent = "";
}

intentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (intentBusy) return;

  const question = intentQuestionInput.value.trim();
  if (!question) return;

  setIntentBusy(true);
  intentExtractStatus.textContent = "Calling Vertex Gemini…";
  intentOutputWrap.classList.add("hidden");

  try {
    const response = await apiFetch("/api/intent/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, mode: intentModeSelect.value }),
    });
    const data = await response.json();
    if (!response.ok) {
      const msg = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || data);
      throw new Error(msg);
    }

    const plan = data.plan || {};
    intentOutput.textContent = JSON.stringify(plan, null, 2);
    intentOutputMeta.textContent = [
      `intent: ${plan.intent || "—"}`,
      plan.confidence != null ? `confidence: ${plan.confidence}` : null,
      data.model ? `model: ${data.model}` : null,
    ]
      .filter(Boolean)
      .join(" · ");
    intentOutputWrap.classList.remove("hidden");
    intentExtractStatus.textContent = `Extracted via ${data.source || "vertex_gemini"}`;
  } catch (error) {
    intentExtractStatus.textContent = `Error: ${error.message}`;
  } finally {
    setIntentBusy(false);
  }
});

intentCopyBtn.addEventListener("click", () => {
  const text = intentOutput.textContent;
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    const prev = intentCopyBtn.textContent;
    intentCopyBtn.textContent = "Copied!";
    setTimeout(() => {
      intentCopyBtn.textContent = prev;
    }, 1500);
  });
});

intentClearBtn.addEventListener("click", () => {
  clearIntentOutput();
});
