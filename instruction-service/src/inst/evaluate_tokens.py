"""Request-scoped tokens for lifecycle evaluate OBO forwarding."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluateTokenContext:
    """Human JWT (+ optional calling-service token for nested OBO)."""

    user_token: str | None
    user_session_id: str | None
    authz_service_token: str | None = None
    authz_service_session_id: str | None = None


_CONTEXT: ContextVar[EvaluateTokenContext | None] = ContextVar(
    "instruction_evaluate_token_context",
    default=None,
)


def bind_evaluate_token_context(ctx: EvaluateTokenContext) -> Token:
    return _CONTEXT.set(ctx)


def reset_evaluate_token_context(token: Token) -> None:
    _CONTEXT.reset(token)


def current_evaluate_token_context() -> EvaluateTokenContext | None:
    return _CONTEXT.get()


def resolve_evaluate_token_context(
    *,
    authorization: str | None,
    x_session_id: str | None,
    x_on_behalf_of: str | None,
    x_on_behalf_of_session_id: str | None,
) -> EvaluateTokenContext:
    """Map inbound headers onto authz OBO arguments.

    Direct user call:
      Authorization = user JWT → authz uses svc-instruction + user token

    Nested OBO (payment → instruction):
      Authorization = calling service (svc-payment)
      X-On-Behalf-Of = user JWT
      → authz uses calling service + user so delegated_by_roles keep INSTRUCTION_MARKER
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
            authz_service_token=_strip(authorization),
            authz_service_session_id=x_session_id,
        )

    return EvaluateTokenContext(
        user_token=_strip(authorization),
        user_session_id=x_session_id,
        authz_service_token=None,
        authz_service_session_id=None,
    )
