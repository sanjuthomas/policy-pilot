#!/usr/bin/env bash
# Wipe Mongo / Neo4j / Kafka / ZITADEL volumes, rebuild images, and bring the
# Policy Pilot stack back up in an order that avoids the ZITADEL PAT race
# (app services load login-client.pat once at process start).
#
# Default: empty domain data + ZITADEL demo users only — ready for harness-driven
# end-to-end testing. Optional --with-demo-seed creates sample instructions/
# payments/alerts via ssi-demo-harness/seed-demo-data.sh --seed-only.
#
# Usage (from repo root or anywhere):
#   ./scripts/clean-slate.sh
#   ./scripts/clean-slate.sh --no-build
#   ./scripts/clean-slate.sh --with-demo-seed
#   ./scripts/clean-slate.sh --skip-zitadel-seed   # infra only; you seed users later
#
# Environment overrides:
#   COMPOSE_UP_BUILD=1|0          # default 1 (pass --no-build to force 0)
#   ZITADEL_PAT_WAIT_SECONDS=180  # max wait for login-client.pat
#   HEALTH_WAIT_SECONDS=180       # max wait per health URL
#   ADMIN_USER / ADMIN_PASSWORD   # harness login smoke (default admin-001 / Password1!)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

COMPOSE_UP_BUILD="${COMPOSE_UP_BUILD:-1}"
ZITADEL_PAT_WAIT_SECONDS="${ZITADEL_PAT_WAIT_SECONDS:-180}"
HEALTH_WAIT_SECONDS="${HEALTH_WAIT_SECONDS:-180}"
ADMIN_USER="${ADMIN_USER:-admin-001}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-Password1!}"
HARNESS_URL="${HARNESS_URL:-http://localhost:8091}"
SKIP_ZITADEL_SEED=0
WITH_DEMO_SEED=0

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  echo
  echo "Options:"
  echo "  --no-build            Skip image rebuild (docker compose up -d only)"
  echo "  --with-demo-seed      After clean slate, run harness seed-demo-data --seed-only"
  echo "  --skip-zitadel-seed   Do not create ZITADEL demo users"
  echo "  -h, --help            Show this help"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-build)
      COMPOSE_UP_BUILD=0
      shift
      ;;
    --with-demo-seed)
      WITH_DEMO_SEED=1
      shift
      ;;
    --skip-zitadel-seed)
      SKIP_ZITADEL_SEED=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

log() {
  printf '\n>>> %s\n' "$*"
}

compose() {
  (cd "${REPO_ROOT}" && docker compose "$@")
}

compose_up() {
  local build_flag=()
  if [[ "${COMPOSE_UP_BUILD}" == "1" ]]; then
    build_flag=(--build)
  fi
  compose up -d "${build_flag[@]}" "$@"
}

wait_for_pat() {
  local elapsed=0
  log "Waiting for ZITADEL login-client.pat (max ${ZITADEL_PAT_WAIT_SECONDS}s)"
  while (( elapsed < ZITADEL_PAT_WAIT_SECONDS )); do
    if docker exec zitadel-login sh -c \
      'test -s /zitadel/bootstrap/login-client.pat' >/dev/null 2>&1; then
      local size
      size="$(docker exec zitadel-login wc -c /zitadel/bootstrap/login-client.pat | awk '{print $1}')"
      echo "  PAT ready (${size} bytes) after ${elapsed}s"
      return 0
    fi
    sleep 3
    elapsed=$((elapsed + 3))
    echo "  … still waiting (${elapsed}s)"
  done
  echo "ERROR: login-client.pat not available after ${ZITADEL_PAT_WAIT_SECONDS}s" >&2
  docker compose -f "${REPO_ROOT}/docker-compose.yml" ps || true
  return 1
}

wait_for_url() {
  local url="$1"
  local elapsed=0
  while (( elapsed < HEALTH_WAIT_SECONDS )); do
    if curl -sf -m 3 "${url}" >/dev/null 2>&1; then
      echo "  UP ${url}"
      return 0
    fi
    sleep 3
    elapsed=$((elapsed + 3))
  done
  echo "ERROR: timed out waiting for ${url}" >&2
  return 1
}

seed_zitadel_users() {
  log "Seeding ZITADEL demo users"
  local pat
  pat="$(docker exec zitadel-login cat /zitadel/bootstrap/login-client.pat | tr -d '\n')"
  if [[ -z "${pat}" ]]; then
    echo "ERROR: PAT file is empty" >&2
    return 1
  fi
  (cd "${REPO_ROOT}/zitadel-seed" && ZITADEL_PAT="${pat}" python3 seed.py)
}

verify_empty_stores() {
  log "Verifying empty MongoDB domain collections"
  docker exec mongodb mongosh --quiet --eval '
const names = ["ssi_cash_instructions", "ssi_cash_activities", "security_events"];
for (const name of names) {
  const d = db.getSiblingDB(name);
  const cols = d.getCollectionNames();
  let total = 0;
  const counts = {};
  for (const c of cols) {
    const n = d[c].countDocuments({});
    counts[c] = n;
    total += n;
  }
  print(name + " total=" + total + " " + JSON.stringify(counts));
}
'

  log "Verifying empty Neo4j (graph + vector documents)"
  docker exec neo4j cypher-shell -u neo4j -p devpassword \
    "MATCH (n) RETURN count(n) AS nodes;"
}

smoke_harness_login() {
  log "Smoke: harness login as ${ADMIN_USER}"
  local code
  code="$(curl -sS -o /tmp/clean-slate-login.out -w '%{http_code}' \
    -X POST "${HARNESS_URL}/api/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"user_id\":\"${ADMIN_USER}\",\"password\":\"${ADMIN_PASSWORD}\"}" || true)"
  if [[ "${code}" != "200" ]]; then
    echo "WARNING: harness login HTTP ${code} (check ZITADEL user seed)" >&2
    python3 -c 'import json,sys; p="/tmp/clean-slate-login.out";
import pathlib
t=pathlib.Path(p).read_text() if pathlib.Path(p).exists() else ""
print(t[:200])' 2>/dev/null || true
    return 0
  fi
  python3 -c 'import json; d=json.load(open("/tmp/clean-slate-login.out")); print("  harness login ok, has_session_token=", bool(d.get("session_token")))'
  rm -f /tmp/clean-slate-login.out
}

main() {
  log "Clean slate start ($(date -u +%Y-%m-%dT%H:%M:%SZ))"

  log "Phase 0: stop stack and remove volumes (Mongo, Neo4j, Kafka, ZITADEL, …)"
  compose down -v --remove-orphans

  # Phase 1 — data plane + identity before any app that caches the PAT at import.
  log "Phase 1: start infrastructure + ZITADEL"
  compose_up \
    mongodb mongo-init \
    neo4j \
    kafka kafka-init \
    opa opa-policy-seed \
    opensearch opensearch-dashboards otel-collector \
    zitadel-postgres zitadel-api zitadel-login zitadel-proxy \
    sequence-service

  wait_for_pat

  if [[ "${SKIP_ZITADEL_SEED}" != "1" ]]; then
    seed_zitadel_users
  else
    log "Skipping ZITADEL user seed (--skip-zitadel-seed)"
  fi

  # Phase 2 — domain apps + CDC + indexer (PAT file is present for Settings load).
  log "Phase 2: rebuild/start application services"
  compose_up \
    instruction-service \
    payment-service \
    authorization-service \
    ssi-chat \
    ssi-demo-harness \
    kafka-connect kafka-connect-init \
    ssi-indexer

  log "Phase 3: health checks"
  wait_for_url "http://localhost:8095/health"   # sequence
  wait_for_url "http://localhost:8000/health"   # instruction
  wait_for_url "http://localhost:8093/health"   # payment
  wait_for_url "http://localhost:8094/health"   # authz
  wait_for_url "http://localhost:8091/health"   # harness
  wait_for_url "http://localhost:8092/health"   # chat
  wait_for_url "http://localhost:8090/health"   # indexer

  verify_empty_stores

  if [[ "${SKIP_ZITADEL_SEED}" != "1" ]]; then
    smoke_harness_login
  fi

  if [[ "${WITH_DEMO_SEED}" == "1" ]]; then
    log "Phase 4: demo domain seed (harness actions)"
    "${REPO_ROOT}/ssi-demo-harness/seed-demo-data.sh" --seed-only
  fi

  log "Compose status"
  compose ps --format 'table {{.Name}}\t{{.Status}}'

  cat <<EOF

=== Clean slate ready ===
  Harness:       ${HARNESS_URL}
  Policy Pilot:  http://localhost:8092
  Instructions:  http://localhost:8000/ui/
  Payments:      http://localhost:8093/ui/
  Indexer:       http://localhost:8090
  Neo4j:         http://localhost:7474/browser/  (neo4j / devpassword)

Domain Mongo + Neo4j are empty${WITH_DEMO_SEED:+ (then demo-seeded)}.
ZITADEL users: password Password1! — see docs/domain-models.md
EOF
}

main "$@"
