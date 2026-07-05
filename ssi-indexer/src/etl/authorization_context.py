from __future__ import annotations

import json
from typing import Any


def authorization_from_event(security_event: dict[str, Any]) -> dict[str, Any]:
    details = security_event.get("details") or {}
    auth = details.get("authorization")
    return auth if isinstance(auth, dict) else {}


def authorization_merged_fields(security_event: dict[str, Any]) -> dict[str, Any]:
    """Denormalize authorization context for graph indexing and hybrid search."""
    auth = authorization_from_event(security_event)
    actor = security_event.get("actor") or {}
    event_ctx = security_event.get("event") or {}
    subject = auth.get("subject_at_decision") or {}

    basis = auth.get("allow_basis") or []
    violations = auth.get("violations") or []

    return {
        "timestamp": security_event.get("timestamp"),
        "authorization_summary": auth.get("summary") or event_ctx.get("reason"),
        "authorization_decision": auth.get("decision"),
        "authorization_basis": basis,
        "authorization_violations": violations,
        "authorization_is_alert": auth.get("is_alert"),
        "event_reason": event_ctx.get("reason"),
        "actor_groups": actor.get("groups") or subject.get("groups") or [],
        "actor_covering_lobs": actor.get("covering_lobs")
        or subject.get("covering_lobs")
        or [],
    }


def authorization_search_parts(merged: dict[str, Any]) -> list[str]:
    parts = [
        merged.get("timestamp") or "",
        merged.get("authorization_summary") or "",
        merged.get("authorization_decision") or "",
        merged.get("event_reason") or "",
        " ".join(merged.get("authorization_basis") or []),
        " ".join(merged.get("authorization_violations") or []),
        " ".join(merged.get("actor_groups") or []),
        " ".join(merged.get("actor_covering_lobs") or []),
    ]
    return [str(part) for part in parts if part]


def authorization_neo4j_params(security_event: dict[str, Any]) -> dict[str, Any]:
    auth = authorization_from_event(security_event)
    return {
        "authorization_summary": auth.get("summary"),
        "authorization_decision": auth.get("decision"),
        "authorization_basis": json.dumps(auth.get("allow_basis") or []),
        "authorization_violations": json.dumps(auth.get("violations") or []),
    }


def authorization_from_fact(fact: dict[str, Any]) -> dict[str, Any]:
    auth = fact.get("authorization")
    return auth if isinstance(auth, dict) else {}


def authorization_merged_from_fact(fact: dict[str, Any]) -> dict[str, Any]:
    """Denormalize approval context from an InstructionFact for search/graph indexing."""
    auth = authorization_from_fact(fact)
    snap = fact.get("instruction_snapshot") or {}
    basis = auth.get("allow_basis") or []
    return {
        "approved_at": snap.get("approved_at"),
        "rejected_at": snap.get("rejected_at"),
        "submitted_at": snap.get("submitted_at"),
        "cancelled_at": snap.get("cancelled_at"),
        "rejection_reason": snap.get("rejection_reason"),
        "authorization_summary": auth.get("summary"),
        "authorization_decision": auth.get("decision"),
        "authorization_basis": basis,
        "authorization_violations": auth.get("violations") or [],
        "authorization_is_alert": auth.get("is_alert"),
    }


def authorization_fact_neo4j_params(fact: dict[str, Any]) -> dict[str, Any]:
    auth = authorization_from_fact(fact)
    snap = fact.get("instruction_snapshot") or {}
    basis = auth.get("allow_basis") or []
    return {
        "approved_at": snap.get("approved_at") or "",
        "submitted_at": snap.get("submitted_at") or "",
        "rejected_at": snap.get("rejected_at") or "",
        "cancelled_at": snap.get("cancelled_at") or "",
        "authorization_summary": auth.get("summary"),
        "authorization_basis": json.dumps(basis) if basis else None,
    }
