#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3.12}"

run_project() {
  local dir="$1"
  local pkg="$2"
  local fail_under="${3:-80}"
  echo ""
  echo "========== ${dir} (${pkg}) =========="
  cd "${ROOT}/${dir}"
  if [[ -f pyproject.toml ]]; then
    $PYTHON -m pip install -e ".[dev]" -q 2>/dev/null \
      || $PYTHON -m pip install -e ".[regression]" -q 2>/dev/null \
      || $PYTHON -m pip install -e . -q
  fi
  local cov_args=(--cov="${pkg}" --cov-report=term-missing)
  if [[ "${fail_under}" != "0" ]]; then
    cov_args+=(--cov-fail-under="${fail_under}")
  fi
  $PYTHON -m pytest tests/ -q "${cov_args[@]}"
}

run_project shared/platform_auth platform_auth
run_project shared/telemetry telemetry
run_project instruction-service inst
run_project payment-service ps
run_project authorization-service authz
run_project ssi-indexer etl
run_project ssi-chat chat_application
# Harness is exempt from the coverage gate (integration/demo tooling).
run_project ssi-demo-harness harness 0

echo ""
echo "All gated projects meet >=80% unit test coverage."
