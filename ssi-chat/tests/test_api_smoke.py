from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.integration
def test_api_smoke_suite() -> None:
    if os.environ.get("RUN_API_SMOKE") != "1":
        pytest.skip("set RUN_API_SMOKE=1 to run live API smoke checks")

    cmd = [
        sys.executable,
        "-m",
        "regression.runner",
        "--api-smoke-only",
        "--chat-url",
        os.environ.get("CHAT_URL", "http://localhost:8092"),
        "--harness-url",
        os.environ.get("HARNESS_URL", "http://localhost:8091"),
        "--instruction-service-url",
        os.environ.get(
            "INSTRUCTION_SERVICE_URL",
            os.environ.get("ILM_URL", "http://localhost:8000"),
        ),
        "--payment-url",
        os.environ.get("PAYMENT_URL", "http://localhost:8093"),
        "--indexer-url",
        os.environ.get("INDEXER_URL", "http://localhost:8090"),
        "--authz-url",
        os.environ.get("AUTHZ_URL", "http://localhost:8094"),
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)

    completed = subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    print(completed.stdout)
    if completed.stderr:
        print(completed.stderr, file=sys.stderr)

    assert completed.returncode == 0, "API smoke suite failed"
