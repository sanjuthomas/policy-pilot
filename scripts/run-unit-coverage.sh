#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3.12}"

run_project() {
  local dir="$1"
  local pkg="$2"
  echo ""
  echo "========== ${dir} (${pkg}) =========="
  cd "${ROOT}/${dir}"
  if [[ -f pyproject.toml ]]; then
    $PYTHON -m pip install -e ".[dev]" -q 2>/dev/null \
      || $PYTHON -m pip install -e ".[regression]" -q 2>/dev/null \
      || $PYTHON -m pip install -e . -q
  fi
  $PYTHON -m pytest tests/ -q --cov="${pkg}" --cov-report=term-missing --cov-fail-under=70
}

run_project shared/platform_auth platform_auth
run_project shared/cypher_gen cypher_gen
run_project shared/telemetry telemetry
run_project instruction-service ilm
run_project payment-service ps
run_project authorization-service authz
run_project ssi-indexer etl
run_project ssi-chat chat_application
run_project ssi-demo-harness harness

echo ""
echo "All projects meet >=70% unit test coverage."
