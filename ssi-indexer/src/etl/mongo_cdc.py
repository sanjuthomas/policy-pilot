"""Normalize MongoDB CDC documents from Kafka Connect into ETL payloads.

Kafka Connect publishes raw Mongo documents (no transforms). This module runs in
ssi-indexer when a consumer reads a message — e.g. split versioned ``_id`` values
like ``instruction_id|version`` into entity ids for pipelines and search profiles.
"""

from __future__ import annotations

from typing import Any


def _document_id(document: dict[str, Any]) -> str | None:
    document_key = document.get("_id")
    if document_key is None:
        return None
    if isinstance(document_key, dict):
        return str(document_key.get("id", document_key))
    return str(document_key)


def _entity_id_from_version_key(document_key: str) -> str:
    return document_key.rsplit("|", 1)[0]


def _user_ref_actor_fields(snapshot: dict[str, Any], actor_user_id: str) -> dict[str, Any]:
    for key in ("approved_by", "rejected_by", "submitted_by", "cancelled_by", "created_by"):
        user = snapshot.get(key)
        if isinstance(user, dict) and user.get("user_id") == actor_user_id:
            return {
                "actor_user_id": actor_user_id,
                "actor_given_name": user.get("given_name"),
                "actor_family_name": user.get("family_name"),
                "actor_title": user.get("title", ""),
                "actor_lob": user.get("lob"),
                "actor_roles": user.get("roles") or [],
                "actor_supervisor_id": user.get("supervisor_id"),
            }
    return {"actor_user_id": actor_user_id}


def _actor_fields_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    lifecycle_events = snapshot.get("lifecycle_events") or []
    if lifecycle_events:
        last_event = lifecycle_events[-1]
        if isinstance(last_event, dict):
            actor_user_id = last_event.get("actor_user_id")
            if actor_user_id:
                return _user_ref_actor_fields(snapshot, str(actor_user_id))

    created_by = snapshot.get("created_by") or {}
    return {
        "actor_user_id": created_by.get("user_id", "unknown"),
        "actor_given_name": created_by.get("given_name"),
        "actor_family_name": created_by.get("family_name"),
        "actor_title": created_by.get("title", ""),
        "actor_lob": created_by.get("lob"),
        "actor_roles": created_by.get("roles") or [],
        "actor_supervisor_id": created_by.get("supervisor_id"),
    }


def _action_from_snapshot(snapshot: dict[str, Any]) -> str:
    lifecycle_events = snapshot.get("lifecycle_events") or []
    if lifecycle_events:
        last_event = lifecycle_events[-1]
        if isinstance(last_event, dict) and last_event.get("action"):
            return str(last_event["action"])
    return "SYNC"


def normalize_security_event(document: dict[str, Any]) -> dict[str, Any]:
    """Expose ``event_id`` from Mongo ``_id`` for security-event pipelines."""
    normalized = dict(document)
    if "event_id" not in normalized:
        document_id = _document_id(normalized)
        if document_id is not None:
            normalized["event_id"] = document_id
    return normalized


def versioned_instruction_to_fact(document: dict[str, Any]) -> dict[str, Any] | None:
    """Map a versioned instruction Mongo row to an InstructionFact-like payload."""
    document_id = _document_id(document)
    if document_id is None:
        return None

    instruction_id = _entity_id_from_version_key(document_id)
    payload = dict(document.get("payload") or {})
    snapshot = {
        **payload,
        "instruction_id": instruction_id,
        "status": document.get("status") or payload.get("status"),
        "owning_lob": document.get("owning_lob") or payload.get("owning_lob"),
        "wire_scope": document.get("wire_scope") or payload.get("wire_scope"),
        "used_by": payload.get("used_by"),
    }
    actor_fields = _actor_fields_from_snapshot(snapshot)

    return {
        "instruction_id": instruction_id,
        "version_number": document.get("version_number"),
        "action": _action_from_snapshot(snapshot),
        "timestamp": document.get("in"),
        "valid_in": document.get("in"),
        "valid_out": document.get("out"),
        **actor_fields,
        "instruction_snapshot": snapshot,
        "authorization": None,
    }


def versioned_payment_to_fact(document: dict[str, Any]) -> dict[str, Any] | None:
    """Map a versioned payment Mongo row to a payment-fact payload."""
    document_id = _document_id(document)
    if document_id is None:
        return None

    payment_id = _entity_id_from_version_key(document_id)
    payload = dict(document.get("payload") or {})
    snapshot = {
        **payload,
        "payment_id": payment_id,
        "status": document.get("status") or payload.get("status"),
        "owning_lob": document.get("owning_lob") or payload.get("owning_lob"),
        "instruction_id": document.get("instruction_id") or payload.get("instruction_id"),
    }
    action = _action_from_snapshot(snapshot)
    fact = {
        **payload,
        "payment_id": payment_id,
        "action": action,
        **_payment_actor_fields(snapshot, action),
    }
    if document.get("version_number") is not None:
        fact["version_number"] = document["version_number"]
    if document.get("status"):
        fact["status"] = document["status"]
    if document.get("owning_lob"):
        fact["owning_lob"] = document["owning_lob"]
    if document.get("instruction_id"):
        fact["instruction_id"] = document["instruction_id"]
    if document.get("in"):
        fact["timestamp"] = document["in"]
        fact["valid_in"] = document["in"]
    if document.get("out"):
        fact["valid_out"] = document["out"]
    return fact


def _payment_actor_fields(snapshot: dict[str, Any], action: str) -> dict[str, Any]:
    """Map payment lifecycle action to the acting user ref on the snapshot."""
    action_to_field = {
        "CREATE_PAYMENT": "created_by",
        "SUBMIT_PAYMENT": "submitted_by",
        "APPROVE_PAYMENT": "approved_by",
        "REJECT_PAYMENT": "rejected_by",
        "CANCEL_PAYMENT": "cancelled_by",
    }
    field = action_to_field.get(action)
    if field:
        user = snapshot.get(field)
        if isinstance(user, dict) and user.get("user_id"):
            return {
                "actor_user_id": user["user_id"],
                "actor_given_name": user.get("given_name"),
                "actor_family_name": user.get("family_name"),
                "actor_title": user.get("title", ""),
                "actor_lob": user.get("lob"),
                "actor_roles": user.get("roles") or [],
                "actor_supervisor_id": user.get("supervisor_id"),
            }
    return _actor_fields_from_snapshot(snapshot)


def normalize_instruction_message(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    if "instruction_id" in payload:
        return payload
    if "payload" in payload or _document_id(payload):
        return versioned_instruction_to_fact(payload)
    return None


def normalize_payment_message(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    if "payment_id" in payload and "payload" not in payload:
        return payload
    if "payload" in payload or _document_id(payload):
        return versioned_payment_to_fact(payload)
    return None
