"""Detect vendor / Gemini capacity failures for user-facing retry UX."""

from __future__ import annotations

GEMINI_RATE_LIMIT_RETRY_SECONDS = 30

GEMINI_RATE_LIMIT_ANSWER = (
    "Google Gemini (our answer model) is temporarily under stress "
    "(HTTP 429 · Resource Exhausted). "
    "Vendor capacity recovered slowly — please wait about 30 seconds, "
    "then retry the same question."
)

_INTENT_ID = "llm.rate_limited"


def gemini_rate_limit_intent_id() -> str:
    return _INTENT_ID


def is_gemini_rate_limit_error(exc: BaseException | None) -> bool:
    """True when ``exc`` (or a nested cause) looks like Vertex/Gemini HTTP 429."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        code = getattr(current, "code", None)
        if code == 429:
            return True
        status = getattr(current, "status", None)
        if status in (429, "RESOURCE_EXHAUSTED", "429"):
            return True
        status_code = getattr(current, "status_code", None)
        if status_code == 429:
            return True
        message = str(current).upper()
        if "RESOURCE_EXHAUSTED" in message:
            return True
        if "429" in message and (
            "RESOURCE" in message or "QUOTA" in message or "RATE" in message
        ):
            return True
        current = current.__cause__ or current.__context__
    return False
