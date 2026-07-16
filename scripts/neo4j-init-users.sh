#!/usr/bin/env bash
# Bootstrap Neo4j Enterprise service accounts (least privilege).
# Requires Neo4j Enterprise (RBAC). Idempotent — safe to re-run after clean slate.
set -euo pipefail

NEO4J_HOST="${NEO4J_HOST:-neo4j}"
NEO4J_BOLT_PORT="${NEO4J_BOLT_PORT:-7687}"
NEO4J_ADMIN_USER="${NEO4J_ADMIN_USER:-neo4j}"
NEO4J_ADMIN_PASSWORD="${NEO4J_ADMIN_PASSWORD:-devpassword}"

NEO4J_CHAT_PASSWORD="${NEO4J_CHAT_PASSWORD:-Password1!}"
NEO4J_INDEXER_PASSWORD="${NEO4J_INDEXER_PASSWORD:-Password1!}"
NEO4J_HARNESS_PASSWORD="${NEO4J_HARNESS_PASSWORD:-Password1!}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CYPHER_FILE="${NEO4J_INIT_CYPHER:-${SCRIPT_DIR}/../neo4j-graph-model/init-service-accounts.cypher}"

if [[ ! -f "${CYPHER_FILE}" ]]; then
  echo "ERROR: missing ${CYPHER_FILE}" >&2
  exit 1
fi

# Escape single quotes for Cypher string literals.
_cypher_escape() {
  printf '%s' "${1//\'/\\\'}"
}

CHAT_ESC="$(_cypher_escape "${NEO4J_CHAT_PASSWORD}")"
INDEXER_ESC="$(_cypher_escape "${NEO4J_INDEXER_PASSWORD}")"
HARNESS_ESC="$(_cypher_escape "${NEO4J_HARNESS_PASSWORD}")"

TMP_CYPHER="$(mktemp)"
trap 'rm -f "${TMP_CYPHER}"' EXIT

sed \
  -e "s|__CHAT_PASSWORD__|${CHAT_ESC}|g" \
  -e "s|__INDEXER_PASSWORD__|${INDEXER_ESC}|g" \
  -e "s|__HARNESS_PASSWORD__|${HARNESS_ESC}|g" \
  "${CYPHER_FILE}" > "${TMP_CYPHER}"

bolt_addr="bolt://${NEO4J_HOST}:${NEO4J_BOLT_PORT}"

echo "Waiting for Neo4j ${bolt_addr}…"
ready=0
for _ in $(seq 1 60); do
  if cypher-shell -a "${bolt_addr}" \
    -u "${NEO4J_ADMIN_USER}" -p "${NEO4J_ADMIN_PASSWORD}" \
    --database system \
    "SHOW CURRENT USER YIELD user RETURN user;" \
    >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done

if [[ "${ready}" != "1" ]]; then
  echo "ERROR: Neo4j not ready for service-account bootstrap" >&2
  exit 1
fi

echo "Applying service accounts…"
cypher-shell -a "${bolt_addr}" \
  -u "${NEO4J_ADMIN_USER}" -p "${NEO4J_ADMIN_PASSWORD}" \
  --database system \
  -f "${TMP_CYPHER}"

# Re-apply passwords when rotating secrets (ignore "old password == new password").
_set_password() {
  local user="$1"
  local password="$2"
  local escaped
  escaped="$(_cypher_escape "${password}")"
  if ! cypher-shell -a "${bolt_addr}" \
    -u "${NEO4J_ADMIN_USER}" -p "${NEO4J_ADMIN_PASSWORD}" \
    --database system \
    "ALTER USER ${user} SET PASSWORD '${escaped}' CHANGE NOT REQUIRED;" \
    >/dev/null 2>&1; then
    echo "  note: password for ${user} unchanged or already set"
  else
    echo "  password refreshed for ${user}"
  fi
}

_set_password svc_chat "${NEO4J_CHAT_PASSWORD}"
_set_password svc_indexer "${NEO4J_INDEXER_PASSWORD}"
_set_password svc_harness "${NEO4J_HARNESS_PASSWORD}"

echo "Verifying service users…"
cypher-shell -a "${bolt_addr}" \
  -u "${NEO4J_ADMIN_USER}" -p "${NEO4J_ADMIN_PASSWORD}" \
  --database system \
  "SHOW USERS YIELD user WHERE user IN ['svc_chat', 'svc_indexer', 'svc_harness'] RETURN user ORDER BY user;"

echo "Neo4j service accounts ready."
