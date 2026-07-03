#!/bin/sh
set -eu

CONNECT_URL="${CONNECT_URL:-http://kafka-connect:8083}"

echo "Waiting for Kafka Connect at ${CONNECT_URL}..."
until curl -sf "${CONNECT_URL}/connectors" >/dev/null; do
  sleep 2
done

for config in /connectors/*.json; do
  name=$(basename "$config" .json)
  echo "Registering connector ${name}"
  curl -sf -X DELETE "${CONNECT_URL}/connectors/${name}" >/dev/null 2>&1 || true
  if ! curl -sf -X POST \
    -H "Content-Type: application/json" \
    --data @"${config}" \
    "${CONNECT_URL}/connectors" >/dev/null; then
    echo "Failed to register ${name}" >&2
    curl -s -X POST -H "Content-Type: application/json" --data @"${config}" "${CONNECT_URL}/connectors" >&2 || true
    exit 1
  fi
  echo "Registered ${name}"
done

echo "All MongoDB source connectors registered."
