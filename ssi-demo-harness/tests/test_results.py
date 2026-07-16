from __future__ import annotations

from harness.results import HarnessActionResult


def test_harness_action_result_to_dict() -> None:
    result = HarnessActionResult(
        action="create_instructions",
        requested=3,
        succeeded=2,
        failed=1,
        logs=["ok", "fail"],
        ok=False,
    )
    payload = result.to_dict()
    assert payload["action"] == "create_instructions"
    assert payload["requested"] == 3
    assert payload["succeeded"] == 2
    assert payload["failed"] == 1
    assert payload["ok"] is False
    assert payload["logs"] == ["ok", "fail"]
    assert payload["context"] == {}
