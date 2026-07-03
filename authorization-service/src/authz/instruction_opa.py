from __future__ import annotations

from typing import Any


def _ensure_rfc3339_z(value: str) -> str:
    if not value:
        return value
    if value.endswith("Z"):
        return value
    if "+" in value or value.count("-") > 2 and "T" in value and value[-6] in "+-":
        return value
    return f"{value}Z"


def build_instruction_opa_context(instruction: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Map an instruction-service document to OPA instruction/account inputs."""
    created_by = instruction.get("created_by") or {}
    funding_account = instruction.get("funding_account") or {}
    owning_lob = instruction.get("owning_lob", "")

    opa_instruction = {
        "status": instruction.get("status"),
        "type": instruction.get("instruction_type"),
        "owning_lob": owning_lob,
        "effective_date": _ensure_rfc3339_z(str(instruction.get("effective_date") or "")),
        "end_date": _ensure_rfc3339_z(str(instruction.get("end_date") or "")),
        "created_by": {
            "user_id": created_by.get("user_id", ""),
            "title": created_by.get("title", ""),
            "supervisor_id": created_by.get("supervisor_id"),
        },
        "suspended_by": instruction.get("suspended_by"),
    }
    opa_account = {
        "owning_lob": funding_account.get("owning_lob") or owning_lob,
    }
    return opa_instruction, opa_account


def instruction_opa_context_for_approval_eligibility(
    instruction: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    """Build OPA inputs for who can approve *right now* (actual lifecycle status)."""
    opa_instruction, opa_account = build_instruction_opa_context(instruction)
    status = str(instruction.get("status") or "")
    if status != "DRAFT":
        return opa_instruction, opa_account, None

    return opa_instruction, opa_account, (
        "Approval is not permitted while status is DRAFT. Submit the instruction first."
    )


def instruction_opa_context_after_submission(
    instruction: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]] | tuple[None, None]:
    """Hypothetical OPA inputs for DRAFT instructions once submitted."""
    status = str(instruction.get("status") or "")
    if status != "DRAFT":
        return None, None

    opa_instruction, opa_account = build_instruction_opa_context(instruction)
    return {**opa_instruction, "status": "SUBMITTED"}, opa_account
