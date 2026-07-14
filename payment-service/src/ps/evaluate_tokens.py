"""Request-scoped tokens for lifecycle evaluate OBO forwarding."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluateTokenContext:
    user_token: str | None
    user_session_id: str | None


_CONTEXT: ContextVar[EvaluateTokenContext | None] = ContextVar(
    "payment_evaluate_token_context",
    default=None,
)


def bind_evaluate_token_context(ctx: EvaluateTokenContext) -> Token:
    return _CONTEXT.set(ctx)


def reset_evaluate_token_context(token: Token) -> None:
    _CONTEXT.reset(token)


def current_evaluate_token_context() -> EvaluateTokenContext | None:
    return _CONTEXT.get()
