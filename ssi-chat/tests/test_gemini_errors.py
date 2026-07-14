from __future__ import annotations

from chat_application.gemini.errors import (
    GEMINI_RATE_LIMIT_RETRY_SECONDS,
    gemini_rate_limit_intent_id,
    is_gemini_rate_limit_error,
)


def test_detects_resource_exhausted_message() -> None:
    exc = RuntimeError(
        "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, "
        "'message': 'Resource exhausted. Please try again later.', "
        "'status': 'RESOURCE_EXHAUSTED'}}"
    )
    assert is_gemini_rate_limit_error(exc)
    assert gemini_rate_limit_intent_id() == "llm.rate_limited"
    assert GEMINI_RATE_LIMIT_RETRY_SECONDS == 30


def test_detects_code_attribute() -> None:
    class ClientError(Exception):
        def __init__(self) -> None:
            super().__init__("quota")
            self.code = 429

    assert is_gemini_rate_limit_error(ClientError())


def test_detects_nested_cause() -> None:
    root = RuntimeError("boom")
    root.__cause__ = RuntimeError("429 RESOURCE_EXHAUSTED")
    assert is_gemini_rate_limit_error(root)


def test_ignores_unrelated_errors() -> None:
    assert not is_gemini_rate_limit_error(RuntimeError("neo4j connection refused"))
    assert not is_gemini_rate_limit_error(None)
