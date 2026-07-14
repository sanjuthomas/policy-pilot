from __future__ import annotations

from inst.evaluate_tokens import EvaluateTokenContext, resolve_evaluate_token_context


def test_resolve_direct_user_call() -> None:
    ctx = resolve_evaluate_token_context(
        authorization="Bearer user-jwt",
        x_session_id="user-sess",
        x_on_behalf_of=None,
        x_on_behalf_of_session_id=None,
    )
    assert ctx == EvaluateTokenContext(
        user_token="user-jwt",
        user_session_id="user-sess",
        authz_service_token=None,
        authz_service_session_id=None,
    )


def test_resolve_nested_obo_preserves_calling_service() -> None:
    ctx = resolve_evaluate_token_context(
        authorization="Bearer svc-payment-jwt",
        x_session_id="svc-sess",
        x_on_behalf_of="user-jwt",
        x_on_behalf_of_session_id="user-sess",
    )
    assert ctx.user_token == "user-jwt"
    assert ctx.user_session_id == "user-sess"
    assert ctx.authz_service_token == "svc-payment-jwt"
    assert ctx.authz_service_session_id == "svc-sess"
