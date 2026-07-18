"""Request-scoped tokens for lifecycle evaluate OBO forwarding."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluateTokenContext:
    """Human JWT for authz OBO (+ optional inbound service token)."""

    user_token: str | None
    user_session_id: str | None


def resolve_evaluate_token_context(
    *,
    authorization: str | None,
    x_session_id: str | None,
    x_on_behalf_of: str | None,
    x_on_behalf_of_session_id: str | None,
) -> EvaluateTokenContext:
    """Map inbound headers onto authz OBO arguments.

    Required pattern:
      Authorization = calling service JWT
      X-On-Behalf-Of = user JWT
    """

    def _strip(value: str | None) -> str | None:
        if not value:
            return None
        text = value.strip()
        if text.lower().startswith("bearer "):
            return text.split(" ", 1)[1].strip()
        return text

    if x_on_behalf_of and str(x_on_behalf_of).strip():
        return EvaluateTokenContext(
            user_token=_strip(x_on_behalf_of),
            user_session_id=x_on_behalf_of_session_id,
        )

    # Fallback only for non-OBO contexts (should not happen once get_subject
    # requires OBO); keep for clarity if headers mode ever forwards tokens.
    return EvaluateTokenContext(
        user_token=_strip(authorization),
        user_session_id=x_session_id,
    )
