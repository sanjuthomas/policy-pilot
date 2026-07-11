from __future__ import annotations

import runpy
from pathlib import Path


def test_policy_catalog_aligned_with_lifecycle() -> None:
    script = (
        Path(__file__).resolve().parents[2]
        / "opa-policy-seed"
        / "validate_policy_catalog.py"
    )
    assert script.is_file(), f"missing validator at {script}"
    namespace = runpy.run_path(str(script))
    assert namespace["main"]() == 0
