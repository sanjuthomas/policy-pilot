from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.integration
def test_chat_regression_suite() -> None:
    if os.environ.get("RUN_CHAT_REGRESSION") != "1":
        pytest.skip("set RUN_CHAT_REGRESSION=1 to run live chat regression")

    cmd = [
        sys.executable,
        "-m",
        "regression.runner",
        "--chat-url",
        os.environ.get("CHAT_URL", "http://localhost:8092"),
        "--harness-url",
        os.environ.get("HARNESS_URL", "http://localhost:8091"),
        "--report",
        str(ROOT / "regression-report.json"),
    ]

    # Seed is on by default in the runner; opt out with CHAT_REGRESSION_SEED=0.
    if os.environ.get("CHAT_REGRESSION_SEED", "1") == "0":
        cmd.append("--no-seed")

    mode = os.environ.get("CHAT_REGRESSION_MODE")
    if mode:
        cmd.extend(["--mode", mode])

    tags = os.environ.get("CHAT_REGRESSION_TAGS")
    if tags:
        cmd.extend(["--tags", tags])

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

    assert completed.returncode == 0, "chat regression suite failed"
