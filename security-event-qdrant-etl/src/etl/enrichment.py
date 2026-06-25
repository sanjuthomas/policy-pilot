from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EnrichedSecurityEventDocument(BaseModel):
    """Security event merged with the current instruction from ILM API."""

    event_id: str
    instruction_id: str
    version_number: int | None = None
    security_event: dict[str, Any]
    instruction: dict[str, Any] | None = None
    merged: dict[str, Any] = Field(
        default_factory=dict,
        description="Denormalized actor + instruction parties for analytics and search",
    )
    search_text: str = Field(
        description="Flattened text used for dense embeddings and BM25 lexical index"
    )


def build_merged_context(
    security_event: dict[str, Any],
    instruction: dict[str, Any] | None,
) -> dict[str, Any]:
    actor = security_event.get("actor") or {}
    resource = security_event.get("resource") or {}
    event_ctx = security_event.get("event") or {}
    instr = instruction or {}

    created_by = instr.get("created_by") or {}
    approved_by = instr.get("approved_by") or {}
    rejected_by = instr.get("rejected_by") or {}

    return {
        "timestamp": security_event.get("timestamp"),
        "severity": security_event.get("severity"),
        "message": security_event.get("message"),
        "action": event_ctx.get("action"),
        "outcome": event_ctx.get("outcome"),
        "reason": event_ctx.get("reason"),
        # Actor (subject who performed the action)
        "actor_user_id": actor.get("user_id"),
        "actor_title": actor.get("title"),
        "actor_roles": actor.get("roles") or [],
        "actor_lob": actor.get("lob"),
        "actor_supervisor_id": actor.get("supervisor_id"),
        # Instruction metadata
        "instruction_id": resource.get("id") or instr.get("instruction_id"),
        "version_number": resource.get("version_number") or instr.get("version_number"),
        "instruction_type": instr.get("instruction_type") or resource.get("instruction_type"),
        "wire_scope": instr.get("wire_scope"),
        "owning_lob": instr.get("owning_lob") or resource.get("owning_lob"),
        "status": instr.get("status") or resource.get("status"),
        "currency": instr.get("currency"),
        "effective_date": instr.get("effective_date"),
        "end_date": instr.get("end_date"),
        "usage_count": instr.get("usage_count"),
        # Instruction parties (full detail for graph traversal queries)
        "creator_user_id": created_by.get("user_id"),
        "creator_title": created_by.get("title"),
        "creator_lob": created_by.get("lob"),
        "creator_supervisor_id": created_by.get("supervisor_id"),
        "approver_user_id": approved_by.get("user_id"),
        "approver_title": approved_by.get("title"),
        "approver_lob": approved_by.get("lob"),
        "approver_supervisor_id": approved_by.get("supervisor_id"),
        "rejector_user_id": rejected_by.get("user_id"),
        "rejector_title": rejected_by.get("title"),
        "rejector_lob": rejected_by.get("lob"),
        "rejector_supervisor_id": rejected_by.get("supervisor_id"),
    }


def build_search_text(
    security_event: dict[str, Any],
    instruction: dict[str, Any] | None,
    merged: dict[str, Any] | None = None,
) -> str:
    ctx = merged or build_merged_context(security_event, instruction)
    parts = [
        ctx.get("message", ""),
        ctx.get("severity", ""),
        ctx.get("action", ""),
        ctx.get("outcome", ""),
        ctx.get("reason") or "",
        ctx.get("actor_user_id", ""),
        ctx.get("actor_title", ""),
        " ".join(ctx.get("actor_roles") or []),
        ctx.get("actor_lob") or "",
        ctx.get("actor_supervisor_id") or "",
        ctx.get("owning_lob", ""),
        ctx.get("status", ""),
        ctx.get("instruction_type") or "",
        ctx.get("wire_scope", ""),
        ctx.get("currency", ""),
        ctx.get("creator_user_id", ""),
        ctx.get("creator_title", ""),
        ctx.get("creator_lob") or "",
        ctx.get("approver_user_id", ""),
        ctx.get("approver_title", ""),
        ctx.get("approver_lob") or "",
        ctx.get("rejector_user_id", ""),
        ctx.get("rejector_title", ""),
        ctx.get("rejector_lob") or "",
        ctx.get("effective_date", ""),
        ctx.get("end_date", ""),
    ]
    return " ".join(str(part) for part in parts if part).strip()


def enrich_document(
    security_event: dict[str, Any],
    instruction: dict[str, Any] | None,
) -> EnrichedSecurityEventDocument:
    resource = security_event.get("resource") or {}
    instruction_id = resource.get("id", "")
    version_number = resource.get("version_number")
    if instruction:
        version_number = instruction.get("version_number", version_number)

    merged = build_merged_context(security_event, instruction)

    return EnrichedSecurityEventDocument(
        event_id=security_event["event_id"],
        instruction_id=instruction_id,
        version_number=version_number,
        security_event=security_event,
        instruction=instruction,
        merged=merged,
        search_text=build_search_text(security_event, instruction, merged),
    )
