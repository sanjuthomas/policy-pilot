from __future__ import annotations

import copy
import logging
from typing import Any

from inst.authorization import (
    build_authorization_block,
    details_with_authorization,
    instruction_resource_context,
)
from inst.models.api import Subject
from inst.models.enums import InstructionStatus, LifecycleAction
from inst.models.instruction import CashSettlementInstruction
from inst.opa import OpaClient

logger = logging.getLogger(__name__)

_REPAIRABLE_ACTIONS = {
    LifecycleAction.CREATE,
    LifecycleAction.UPDATE,
    LifecycleAction.DELETE,
    LifecycleAction.SUBMIT,
    LifecycleAction.APPROVE,
    LifecycleAction.REJECT,
    LifecycleAction.SUSPEND,
    LifecycleAction.REACTIVATE,
    LifecycleAction.USE,
}


def _subject_from_actor(actor: dict[str, Any]) -> Subject:
    return Subject(
        user_id=actor["user_id"],
        given_name=actor.get("given_name"),
        family_name=actor.get("family_name"),
        title=actor.get("title") or "",
        lob=actor.get("lob"),
        roles=list(actor.get("roles") or []),
        groups=list(actor.get("groups") or []),
        supervisor_id=actor.get("supervisor_id"),
        delegated_by=actor.get("delegated_by"),
        delegated_by_roles=list(actor.get("delegated_by_roles") or []),
    )


def _instruction_for_opa_replay(
    snapshot: dict[str, Any],
    action: LifecycleAction,
) -> CashSettlementInstruction:
    """Rewind post-mutation snapshots so OPA sees pre-transition instruction state."""
    snap = copy.deepcopy(snapshot)

    if action == LifecycleAction.APPROVE:
        snap["status"] = InstructionStatus.PENDING.value
        snap.pop("approved_by", None)
        snap.pop("approved_at", None)
    elif action == LifecycleAction.SUBMIT:
        snap["status"] = InstructionStatus.DRAFT.value
        snap.pop("submitted_at", None)
    elif action == LifecycleAction.REJECT:
        snap["status"] = InstructionStatus.PENDING.value
        snap.pop("rejected_by", None)
        snap.pop("rejected_at", None)
        snap.pop("rejection_reason", None)
    elif action == LifecycleAction.SUSPEND:
        if snap.get("instruction_type") == "STANDING":
            snap["status"] = InstructionStatus.STANDING.value
        else:
            snap["status"] = InstructionStatus.SINGLE_USE.value
        snap.pop("suspended_by", None)
        snap.pop("suspended_at", None)
    elif action == LifecycleAction.REACTIVATE:
        snap["status"] = InstructionStatus.SUSPENDED.value
    elif action == LifecycleAction.USE:
        usage = int(snap.get("usage_count") or 0)
        snap["usage_count"] = max(usage - 1, 0)
        if snap.get("instruction_type") == "SINGLE_USE" and snap.get("status") == "USED":
            snap["status"] = InstructionStatus.SINGLE_USE.value

    return CashSettlementInstruction.model_validate(snap)


async def repair_security_event_authorization(
    document: dict[str, Any],
    *,
    opa: OpaClient | None = None,
) -> dict[str, Any] | None:
    """Recompute and attach missing OPA authorization on a stored security event."""
    details = document.get("details") or {}
    if details.get("authorization"):
        return None

    event_ctx = document.get("event") or {}
    if event_ctx.get("outcome") != "success":
        return None

    action_str = event_ctx.get("action")
    if not action_str:
        return None

    try:
        action = LifecycleAction(action_str)
    except ValueError:
        return None

    if action not in _REPAIRABLE_ACTIONS:
        return None

    snapshot = document.get("instruction_snapshot")
    actor = document.get("actor") or {}
    if not snapshot or not actor.get("user_id"):
        return None

    client = opa or OpaClient()
    subject = _subject_from_actor(actor)
    instruction = _instruction_for_opa_replay(snapshot, action)
    decision = await client.evaluate(action, subject, instruction)
    authorization = build_authorization_block(
        decision,
        subject,
        action,
        resource_context=instruction_resource_context(instruction),
    )

    if not decision.allowed:
        logger.warning(
            "authorization repair OPA replay denied action=%s event_id=%s summary=%s",
            action.value,
            document.get("event_id"),
            authorization.get("summary"),
        )
        return None

    repaired = copy.deepcopy(document)
    repaired["details"] = details_with_authorization(details, authorization)
    repaired["event"] = {**event_ctx, "reason": authorization["summary"]}
    return repaired
