from __future__ import annotations

from telemetry import get_meter, record_counter, record_histogram

_meter = None


def _get_meter():
    global _meter
    if _meter is None:
        _meter = get_meter("authz.opa", version="0.1.0")
    return _meter


def record_opa_evaluation(package: str, *, allowed: bool, duration_ms: float) -> None:
    """Record an OPA policy evaluation outcome and latency.

    Powers the authorization deny-rate and evaluate-latency SLIs. ``decision``
    is ``allow`` or ``deny``; ``package`` identifies the policy domain
    (e.g. ``payment/lifecycle``).
    """

    decision = "allow" if allowed else "deny"
    attributes = {"authz.decision": decision, "authz.package": package}
    record_counter(_get_meter(), "authz.evaluate.count", attributes=attributes)
    record_histogram(
        _get_meter(),
        "authz.evaluate.duration",
        duration_ms,
        unit="ms",
        attributes=attributes,
    )
