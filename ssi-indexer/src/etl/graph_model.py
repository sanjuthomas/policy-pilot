"""Neo4j graph model constants and action → lifecycle edge mapping."""

from __future__ import annotations

from typing import Any

OPEN_OUT_SENTINEL = "9999-12-31T23:59:59Z"

INSTRUCTION_ACTION_TO_EDGE: dict[str, str] = {
    "CREATE": "CREATED_IV",
    "SUBMIT": "SUBMITTED_IV",
    "APPROVE": "APPROVED_IV",
    "REJECT": "REJECTED_IV",
    "CANCEL": "CANCELLED_IV",
    "SUSPEND": "SUSPENDED_IV",
    "REACTIVATE": "REACTIVATED_IV",
    "USE": "USED_IV",
    "RELEASE_USE": "RELEASED_IV",
}

PAYMENT_ACTION_TO_EDGE: dict[str, str] = {
    "CREATE_PAYMENT": "CREATED_PV",
    "SUBMIT_PAYMENT": "SUBMITTED_PV",
    "APPROVE_PAYMENT": "APPROVED_PV",
    "REJECT_PAYMENT": "REJECTED_PV",
    "CANCEL_PAYMENT": "CANCELLED_PV",
}


def is_version_open(valid_out: str | None) -> bool:
    if not valid_out:
        return True
    return valid_out.startswith(OPEN_OUT_SENTINEL[:10]) or valid_out == OPEN_OUT_SENTINEL


def _lifecycle_event_details(snapshot: dict[str, Any]) -> dict[str, Any]:
    lifecycle_events = snapshot.get("lifecycle_events") or []
    if not lifecycle_events:
        return {}
    last = lifecycle_events[-1]
    if isinstance(last, dict):
        details = last.get("details")
        if isinstance(details, dict):
            return details
    return {}


def instruction_lifecycle_actor(
    fact: dict[str, Any],
) -> tuple[str | None, dict[str, Any]]:
    """Resolve (user_id, extra edge props) for an instruction fact lifecycle edge."""
    action = fact.get("action", "")
    snap = fact.get("instruction_snapshot") or {}
    details = _lifecycle_event_details(snap)

    if action == "CREATE":
        user_id = (snap.get("created_by") or {}).get("user_id")
        return user_id, {}
    if action == "SUBMIT":
        user_id = fact.get("actor_user_id") or (snap.get("submitted_by") or {}).get("user_id")
        return user_id, {}
    if action == "APPROVE":
        user_id = (snap.get("approved_by") or {}).get("user_id") or fact.get("actor_user_id")
        return user_id, {}
    if action == "REJECT":
        user_id = (snap.get("rejected_by") or {}).get("user_id") or fact.get("actor_user_id")
        return user_id, {}
    if action == "CANCEL":
        user_id = fact.get("actor_user_id") or (snap.get("cancelled_by") or {}).get("user_id")
        return user_id, {}
    if action in ("SUSPEND", "REACTIVATE", "RELEASE_USE"):
        return fact.get("actor_user_id"), {}
    if action == "USE":
        user_id = fact.get("actor_user_id")
        payment_id = snap.get("used_by") or details.get("payment_reference")
        delegated_by = details.get("delegated_by")
        props: dict[str, Any] = {}
        if payment_id:
            props["payment_id"] = payment_id
        if delegated_by:
            props["delegated_by"] = delegated_by
        return user_id, props
    return None, {}


def payment_lifecycle_actor(fact: dict[str, Any]) -> str | None:
    """Resolve user_id for a payment fact lifecycle edge."""
    action = fact.get("action", "")
    if action == "CREATE_PAYMENT":
        return (fact.get("created_by") or {}).get("user_id")
    if action == "SUBMIT_PAYMENT":
        return (fact.get("submitted_by") or {}).get("user_id") or fact.get("actor_user_id")
    if action == "APPROVE_PAYMENT":
        return (fact.get("approved_by") or {}).get("user_id") or fact.get("actor_user_id")
    if action == "REJECT_PAYMENT":
        return (fact.get("rejected_by") or {}).get("user_id") or fact.get("actor_user_id")
    if action == "CANCEL_PAYMENT":
        return (fact.get("cancelled_by") or {}).get("user_id") or fact.get("actor_user_id")
    return fact.get("actor_user_id")


def release_use_payment_id(fact: dict[str, Any]) -> str | None:
    """Payment id whose CONSUMED edges should be deleted on RELEASE_USE."""
    details = _lifecycle_event_details(fact.get("instruction_snapshot") or {})
    return details.get("payment_reference")
