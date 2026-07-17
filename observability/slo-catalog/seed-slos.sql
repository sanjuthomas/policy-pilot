-- Policy Pilot OpenSLO catalog seed (Postgres initdb — first volume create only).
-- metricSourceRef "prometheus" must match OBSERVABILITY_MESH_SLO_PROVISIONER_DATASOURCE_NAMES.
--
-- Metric names assume the collector prometheus exporter runs with
-- add_metric_suffixes:false and resource_to_telemetry_conversion:true, so
-- OTLP metrics surface as e.g. http_server_request_duration_{count,bucket}
-- with a service_name label from the OTel resource.

-- ── SLI: chat answer success ─────────────────────────────────────────────────
INSERT INTO service_level_objectives (
  logical_key, version, stale, api_version, kind, name, content, created_by, created_at
) VALUES (
  'openslo/v1/SLI/chat-answer-success',
  1, false, 'openslo/v1', 'SLI', 'chat-answer-success',
  '{
    "apiVersion": "openslo/v1",
    "kind": "SLI",
    "metadata": { "name": "chat-answer-success", "displayName": "Chat answer success" },
    "spec": {
      "description": "Ratio of /api/chat answers that succeed (non-5xx).",
      "ratioMetric": {
        "good": { "metricSource": { "metricSourceRef": "prometheus", "spec": {
          "query": "sum(increase(http_server_request_duration_count{service_name=\"ssi-chat\",url_path=\"/api/chat\",http_response_status_code!~\"5..\"}[5m]))"
        } } },
        "total": { "metricSource": { "metricSourceRef": "prometheus", "spec": {
          "query": "sum(increase(http_server_request_duration_count{service_name=\"ssi-chat\",url_path=\"/api/chat\"}[5m]))"
        } } }
      }
    }
  }'::jsonb,
  'seed', TIMESTAMPTZ '2026-07-16T00:00:00Z'
) ON CONFLICT (logical_key, version) DO NOTHING;

INSERT INTO service_level_objectives (
  logical_key, version, stale, api_version, kind, name, content, created_by, created_at
) VALUES (
  'openslo/v1/SLO/chat-answer-success-30d',
  1, false, 'openslo/v1', 'SLO', 'chat-answer-success-30d',
  '{
    "apiVersion": "openslo/v1",
    "kind": "SLO",
    "metadata": { "name": "chat-answer-success-30d", "displayName": "Chat answer success (30-day rolling)" },
    "spec": {
      "service": "ssi-chat",
      "description": "99.5% of /api/chat answers succeed over a 30-day rolling window.",
      "indicatorRef": "chat-answer-success",
      "timeWindow": [{ "duration": "30d", "isRolling": true }],
      "budgetingMethod": "Occurrences",
      "objectives": [{ "displayName": "Success target", "target": 0.995 }]
    }
  }'::jsonb,
  'seed', TIMESTAMPTZ '2026-07-16T00:00:00Z'
) ON CONFLICT (logical_key, version) DO NOTHING;

-- ── SLI: chat answer latency ≤ 5s ────────────────────────────────────────────
INSERT INTO service_level_objectives (
  logical_key, version, stale, api_version, kind, name, content, created_by, created_at
) VALUES (
  'openslo/v1/SLI/chat-answer-latency-5s',
  1, false, 'openslo/v1', 'SLI', 'chat-answer-latency-5s',
  '{
    "apiVersion": "openslo/v1",
    "kind": "SLI",
    "metadata": { "name": "chat-answer-latency-5s", "displayName": "Chat answer latency under 5s" },
    "spec": {
      "description": "Ratio of /api/chat answers returned within 5000ms.",
      "ratioMetric": {
        "good": { "metricSource": { "metricSourceRef": "prometheus", "spec": {
          "query": "sum(increase(http_server_request_duration_bucket{service_name=\"ssi-chat\",url_path=\"/api/chat\",le=\"5000\"}[5m]))"
        } } },
        "total": { "metricSource": { "metricSourceRef": "prometheus", "spec": {
          "query": "sum(increase(http_server_request_duration_count{service_name=\"ssi-chat\",url_path=\"/api/chat\"}[5m]))"
        } } }
      }
    }
  }'::jsonb,
  'seed', TIMESTAMPTZ '2026-07-16T00:00:00Z'
) ON CONFLICT (logical_key, version) DO NOTHING;

INSERT INTO service_level_objectives (
  logical_key, version, stale, api_version, kind, name, content, created_by, created_at
) VALUES (
  'openslo/v1/SLO/chat-answer-latency-5s-30d',
  1, false, 'openslo/v1', 'SLO', 'chat-answer-latency-5s-30d',
  '{
    "apiVersion": "openslo/v1",
    "kind": "SLO",
    "metadata": { "name": "chat-answer-latency-5s-30d", "displayName": "Chat answer latency ≤5s (30-day rolling)" },
    "spec": {
      "service": "ssi-chat",
      "description": "95% of /api/chat answers return within 5s over a 30-day rolling window.",
      "indicatorRef": "chat-answer-latency-5s",
      "timeWindow": [{ "duration": "30d", "isRolling": true }],
      "budgetingMethod": "Occurrences",
      "objectives": [{ "displayName": "Latency target", "target": 0.95 }]
    }
  }'::jsonb,
  'seed', TIMESTAMPTZ '2026-07-16T00:00:00Z'
) ON CONFLICT (logical_key, version) DO NOTHING;

-- ── SLI: chat answer non-downvote rate ──────────────────────────────────────
-- Users mostly vote when an answer is bad, so explicit downvotes burn budget;
-- upvotes and silence are both treated as good outcomes.
INSERT INTO service_level_objectives (
  logical_key, version, stale, api_version, kind, name, content, created_by, created_at
) VALUES (
  'openslo/v1/SLI/chat-answer-non-downvote',
  1, false, 'openslo/v1', 'SLI', 'chat-answer-non-downvote',
  '{
    "apiVersion": "openslo/v1",
    "kind": "SLI",
    "metadata": { "name": "chat-answer-non-downvote", "displayName": "Chat answer non-downvote rate" },
    "spec": {
      "description": "Ratio of completed chat answers that were not explicitly downvoted. Upvotes and no-votes are good.",
      "ratioMetric": {
        "good": { "metricSource": { "metricSourceRef": "prometheus", "spec": {
          "query": "clamp_min(sum(increase(chat_answer_count[5m])) - (sum(increase(chat_feedback_count{chat_feedback_rating=\"down\"}[5m])) or vector(0)), 0)"
        } } },
        "total": { "metricSource": { "metricSourceRef": "prometheus", "spec": {
          "query": "sum(increase(chat_answer_count[5m]))"
        } } }
      }
    }
  }'::jsonb,
  'seed', TIMESTAMPTZ '2026-07-16T00:00:00Z'
) ON CONFLICT (logical_key, version) DO NOTHING;

INSERT INTO service_level_objectives (
  logical_key, version, stale, api_version, kind, name, content, created_by, created_at
) VALUES (
  'openslo/v1/SLO/chat-answer-non-downvote-30d',
  1, false, 'openslo/v1', 'SLO', 'chat-answer-non-downvote-30d',
  '{
    "apiVersion": "openslo/v1",
    "kind": "SLO",
    "metadata": { "name": "chat-answer-non-downvote-30d", "displayName": "Chat answer non-downvote rate (30-day rolling)" },
    "spec": {
      "service": "ssi-chat",
      "description": "98% of completed chat answers avoid explicit downvotes over a 30-day rolling window. No vote is counted as good because users usually stay silent when an answer is acceptable.",
      "indicatorRef": "chat-answer-non-downvote",
      "timeWindow": [{ "duration": "30d", "isRolling": true }],
      "budgetingMethod": "Occurrences",
      "objectives": [{ "displayName": "Non-downvote target", "target": 0.98 }]
    }
  }'::jsonb,
  'seed', TIMESTAMPTZ '2026-07-16T00:00:00Z'
) ON CONFLICT (logical_key, version) DO NOTHING;

-- ── SLI: authorization evaluate latency ≤ 250ms ──────────────────────────────
INSERT INTO service_level_objectives (
  logical_key, version, stale, api_version, kind, name, content, created_by, created_at
) VALUES (
  'openslo/v1/SLI/authz-evaluate-latency-250ms',
  1, false, 'openslo/v1', 'SLI', 'authz-evaluate-latency-250ms',
  '{
    "apiVersion": "openslo/v1",
    "kind": "SLI",
    "metadata": { "name": "authz-evaluate-latency-250ms", "displayName": "Authorization evaluate under 250ms" },
    "spec": {
      "description": "Ratio of OPA policy evaluations completed within 250ms.",
      "ratioMetric": {
        "good": { "metricSource": { "metricSourceRef": "prometheus", "spec": {
          "query": "sum(increase(authz_evaluate_duration_bucket{le=\"250\"}[5m]))"
        } } },
        "total": { "metricSource": { "metricSourceRef": "prometheus", "spec": {
          "query": "sum(increase(authz_evaluate_duration_count[5m]))"
        } } }
      }
    }
  }'::jsonb,
  'seed', TIMESTAMPTZ '2026-07-16T00:00:00Z'
) ON CONFLICT (logical_key, version) DO NOTHING;

INSERT INTO service_level_objectives (
  logical_key, version, stale, api_version, kind, name, content, created_by, created_at
) VALUES (
  'openslo/v1/SLO/authz-evaluate-latency-250ms-30d',
  1, false, 'openslo/v1', 'SLO', 'authz-evaluate-latency-250ms-30d',
  '{
    "apiVersion": "openslo/v1",
    "kind": "SLO",
    "metadata": { "name": "authz-evaluate-latency-250ms-30d", "displayName": "Authorization evaluate ≤250ms (30-day rolling)" },
    "spec": {
      "service": "authorization-service",
      "description": "99% of OPA evaluations complete within 250ms over a 30-day rolling window.",
      "indicatorRef": "authz-evaluate-latency-250ms",
      "timeWindow": [{ "duration": "30d", "isRolling": true }],
      "budgetingMethod": "Occurrences",
      "objectives": [{ "displayName": "Latency target", "target": 0.99 }]
    }
  }'::jsonb,
  'seed', TIMESTAMPTZ '2026-07-16T00:00:00Z'
) ON CONFLICT (logical_key, version) DO NOTHING;

-- ── SLI: skill execution success ─────────────────────────────────────────────
INSERT INTO service_level_objectives (
  logical_key, version, stale, api_version, kind, name, content, created_by, created_at
) VALUES (
  'openslo/v1/SLI/skill-execution-success',
  1, false, 'openslo/v1', 'SLI', 'skill-execution-success',
  '{
    "apiVersion": "openslo/v1",
    "kind": "SLI",
    "metadata": { "name": "skill-execution-success", "displayName": "Skill execution success" },
    "spec": {
      "description": "Ratio of mutation-skill runs that did not fail with a system error (denials and No Go are healthy outcomes).",
      "ratioMetric": {
        "good": { "metricSource": { "metricSourceRef": "prometheus", "spec": {
          "query": "sum(increase(chat_skill_outcome_count{chat_skill_status!=\"error\"}[5m]))"
        } } },
        "total": { "metricSource": { "metricSourceRef": "prometheus", "spec": {
          "query": "sum(increase(chat_skill_outcome_count[5m]))"
        } } }
      }
    }
  }'::jsonb,
  'seed', TIMESTAMPTZ '2026-07-16T00:00:00Z'
) ON CONFLICT (logical_key, version) DO NOTHING;

INSERT INTO service_level_objectives (
  logical_key, version, stale, api_version, kind, name, content, created_by, created_at
) VALUES (
  'openslo/v1/SLO/skill-execution-success-30d',
  1, false, 'openslo/v1', 'SLO', 'skill-execution-success-30d',
  '{
    "apiVersion": "openslo/v1",
    "kind": "SLO",
    "metadata": { "name": "skill-execution-success-30d", "displayName": "Skill execution success (30-day rolling)" },
    "spec": {
      "service": "ssi-chat",
      "description": "99% of mutation-skill runs avoid system errors over a 30-day rolling window.",
      "indicatorRef": "skill-execution-success",
      "timeWindow": [{ "duration": "30d", "isRolling": true }],
      "budgetingMethod": "Occurrences",
      "objectives": [{ "displayName": "Success target", "target": 0.99 }]
    }
  }'::jsonb,
  'seed', TIMESTAMPTZ '2026-07-16T00:00:00Z'
) ON CONFLICT (logical_key, version) DO NOTHING;

-- ── SLI: platform HTTP success (all services) ────────────────────────────────
INSERT INTO service_level_objectives (
  logical_key, version, stale, api_version, kind, name, content, created_by, created_at
) VALUES (
  'openslo/v1/SLI/platform-http-success',
  1, false, 'openslo/v1', 'SLI', 'platform-http-success',
  '{
    "apiVersion": "openslo/v1",
    "kind": "SLI",
    "metadata": { "name": "platform-http-success", "displayName": "Platform HTTP success" },
    "spec": {
      "description": "Ratio of HTTP requests across all services that succeed (non-5xx).",
      "ratioMetric": {
        "good": { "metricSource": { "metricSourceRef": "prometheus", "spec": {
          "query": "sum(increase(http_server_request_duration_count{http_response_status_code!~\"5..\"}[5m]))"
        } } },
        "total": { "metricSource": { "metricSourceRef": "prometheus", "spec": {
          "query": "sum(increase(http_server_request_duration_count[5m]))"
        } } }
      }
    }
  }'::jsonb,
  'seed', TIMESTAMPTZ '2026-07-16T00:00:00Z'
) ON CONFLICT (logical_key, version) DO NOTHING;

INSERT INTO service_level_objectives (
  logical_key, version, stale, api_version, kind, name, content, created_by, created_at
) VALUES (
  'openslo/v1/SLO/platform-http-success-30d',
  1, false, 'openslo/v1', 'SLO', 'platform-http-success-30d',
  '{
    "apiVersion": "openslo/v1",
    "kind": "SLO",
    "metadata": { "name": "platform-http-success-30d", "displayName": "Platform HTTP success (30-day rolling)" },
    "spec": {
      "service": "policy-pilot",
      "description": "99.9% of HTTP requests succeed (non-5xx) over a 30-day rolling window.",
      "indicatorRef": "platform-http-success",
      "timeWindow": [{ "duration": "30d", "isRolling": true }],
      "budgetingMethod": "Occurrences",
      "objectives": [{ "displayName": "Success target", "target": 0.999 }]
    }
  }'::jsonb,
  'seed', TIMESTAMPTZ '2026-07-16T00:00:00Z'
) ON CONFLICT (logical_key, version) DO NOTHING;

-- ── SLI: indexer consumer success (pipeline freshness proxy) ─────────────────
INSERT INTO service_level_objectives (
  logical_key, version, stale, api_version, kind, name, content, created_by, created_at
) VALUES (
  'openslo/v1/SLI/pipeline-consumer-success',
  1, false, 'openslo/v1', 'SLI', 'pipeline-consumer-success',
  '{
    "apiVersion": "openslo/v1",
    "kind": "SLI",
    "metadata": { "name": "pipeline-consumer-success", "displayName": "Indexer consumer success" },
    "spec": {
      "description": "Ratio of CDC records the indexer processed vs processed-plus-failed.",
      "ratioMetric": {
        "good": { "metricSource": { "metricSourceRef": "prometheus", "spec": {
          "query": "sum(increase(etl_consumer_processed[5m]))"
        } } },
        "total": { "metricSource": { "metricSourceRef": "prometheus", "spec": {
          "query": "sum(increase(etl_consumer_processed[5m])) + sum(increase(etl_consumer_failed[5m]))"
        } } }
      }
    }
  }'::jsonb,
  'seed', TIMESTAMPTZ '2026-07-16T00:00:00Z'
) ON CONFLICT (logical_key, version) DO NOTHING;

INSERT INTO service_level_objectives (
  logical_key, version, stale, api_version, kind, name, content, created_by, created_at
) VALUES (
  'openslo/v1/SLO/pipeline-consumer-success-30d',
  1, false, 'openslo/v1', 'SLO', 'pipeline-consumer-success-30d',
  '{
    "apiVersion": "openslo/v1",
    "kind": "SLO",
    "metadata": { "name": "pipeline-consumer-success-30d", "displayName": "Indexer consumer success (30-day rolling)" },
    "spec": {
      "service": "ssi-indexer",
      "description": "99.9% of CDC records are indexed without landing in the DLQ over a 30-day rolling window.",
      "indicatorRef": "pipeline-consumer-success",
      "timeWindow": [{ "duration": "30d", "isRolling": true }],
      "budgetingMethod": "Occurrences",
      "objectives": [{ "displayName": "Success target", "target": 0.999 }]
    }
  }'::jsonb,
  'seed', TIMESTAMPTZ '2026-07-16T00:00:00Z'
) ON CONFLICT (logical_key, version) DO NOTHING;
