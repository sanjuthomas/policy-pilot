from __future__ import annotations

import logging
from typing import Any

import httpx

from chat_application.config import settings
from chat_application.formatting import (
    format_eligible_approvers_section,
    format_money_amount,
)

logger = logging.getLogger(__name__)


class EligibilityClientError(Exception):
    pass


class EligibilityClient:
    def __init__(
        self,
        *,
        payment_service_url: str | None = None,
        instruction_service_url: str | None = None,
    ) -> None:
        self._payment_base = (payment_service_url or settings.payment_service_url).rstrip("/")
        self._instruction_base = (
            instruction_service_url or settings.instruction_service_url
        ).rstrip("/")

    async def eligible_approvers_for_payment(
        self,
        payment_id: str,
        *,
        bearer_token: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self._payment_base}/api/v1/payments/{payment_id}/eligible-approvers"
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Accept": "application/json",
        }
        if session_id:
            headers["X-Session-Id"] = session_id

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers)

        if response.status_code == 401:
            raise EligibilityClientError("authentication required — log in as a compliance analyst")
        if response.status_code == 403:
            raise EligibilityClientError("COMPLIANCE_ANALYST role required for this question")
        if response.status_code == 404:
            detail = response.json().get("detail", response.text)
            raise EligibilityClientError(str(detail))
        if not response.is_success:
            detail = response.json().get("detail", response.text)
            raise EligibilityClientError(f"payment service error: {detail}")

        return response.json()

    async def eligible_approvers_for_instruction(
        self,
        instruction_id: str,
        *,
        bearer_token: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        url = (
            f"{self._instruction_base}/api/v1/instructions/{instruction_id}/eligible-approvers"
        )
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Accept": "application/json",
        }
        if session_id:
            headers["X-Session-Id"] = session_id

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers)

        if response.status_code == 401:
            raise EligibilityClientError("authentication required — log in as a compliance analyst")
        if response.status_code == 403:
            raise EligibilityClientError("COMPLIANCE_ANALYST role required for this question")
        if response.status_code == 404:
            detail = response.json().get("detail", response.text)
            raise EligibilityClientError(str(detail))
        if not response.is_success:
            detail = response.json().get("detail", response.text)
            raise EligibilityClientError(f"instruction service error: {detail}")

        return response.json()


def _payment_instruction_summary(
    instruction_id: str,
    instruction_status: str,
) -> str:
    instruction_id = str(instruction_id or "").strip()
    if instruction_id:
        return f"backing instruction {instruction_id} ({instruction_status})"
    return f"instruction {instruction_status}"


def format_eligible_approvers_answer(data: dict[str, Any]) -> str:
    payment_id = data.get("payment_id", "")
    status = data.get("payment_status", "")
    amount_text = format_money_amount(data.get("amount"), data.get("currency", ""))
    owning_lob = data.get("owning_lob", "")
    instruction_id = data.get("instruction_id", "")
    instruction_status = data.get("instruction_status", "")
    instruction_summary = _payment_instruction_summary(instruction_id, instruction_status)
    approval_blocked_reason = data.get("approval_blocked_reason")
    prospective = data.get("prospective_eligible") or []

    header = (
        f"Live OPA evaluation for payment {payment_id} "
        f"({status}, {amount_text}, desk {owning_lob}, {instruction_summary})."
    )

    if approval_blocked_reason:
        parts = [header, "", approval_blocked_reason]
        if prospective:
            parts.append(
                format_eligible_approvers_section(
                    header=(
                        "After the payment is submitted (DRAFT → SUBMITTED), these users "
                        "would satisfy APPROVE policy:"
                    ),
                    section_title="",
                    eligible=prospective,
                    empty_message=(
                        "No users would satisfy APPROVE policy after submission."
                    ),
                    candidate_role_label="FUNDING_APPROVER",
                    candidates_evaluated=data.get("candidates_evaluated"),
                )
            )
        return "\n\n".join(parts)

    return format_eligible_approvers_section(
        header=header,
        section_title="Users who can approve this payment:",
        eligible=data.get("eligible") or [],
        empty_message=_payment_eligible_empty_message(
            status,
            instruction_status,
            instruction_id=instruction_id,
        ),
        candidate_role_label="FUNDING_APPROVER",
        candidates_evaluated=data.get("candidates_evaluated"),
    )


def _payment_eligible_empty_message(
    payment_status: str,
    instruction_status: str,
    *,
    instruction_id: str = "",
) -> str:
    instruction_id = str(instruction_id or "").strip()
    instruction_label = (
        f"The backing instruction {instruction_id}"
        if instruction_id
        else "The backing instruction"
    )
    if payment_status == "APPROVED":
        return "This payment is already APPROVED."
    if instruction_status in {"USED", "REJECTED", "EXPIRED", "CANCELLED"}:
        return (
            f"{instruction_label} is {instruction_status} and cannot support "
            "payment approval."
        )
    return "No users currently satisfy APPROVE policy for this payment."


def format_instruction_eligible_approvers_answer(data: dict[str, Any]) -> str:
    instruction_id = data.get("instruction_id", "")
    status = data.get("instruction_status", "")
    instruction_type = data.get("instruction_type", "")
    owning_lob = data.get("owning_lob", "")
    created_by = data.get("created_by_user_id", "")
    creator_title = data.get("created_by_title", "")
    approval_blocked_reason = data.get("approval_blocked_reason")
    prospective = data.get("prospective_eligible") or []

    header = (
        f"Live OPA evaluation for instruction {instruction_id} "
        f"({status}, {instruction_type}, desk {owning_lob}, "
        f"created by {created_by} / {creator_title})."
    )

    if approval_blocked_reason:
        parts = [header, "", approval_blocked_reason]
        if prospective:
            parts.append(
                format_eligible_approvers_section(
                    header="After submission (DRAFT → SUBMITTED), these users would satisfy APPROVE policy:",
                    section_title="",
                    eligible=prospective,
                    empty_message="No users would satisfy APPROVE policy after submission.",
                    candidate_role_label="INSTRUCTION_APPROVER",
                    candidates_evaluated=data.get("candidates_evaluated"),
                )
            )
        return "\n\n".join(parts)

    return format_eligible_approvers_section(
        header=header,
        section_title="Users who can approve this instruction:",
        eligible=data.get("eligible") or [],
        empty_message=_instruction_eligible_empty_message(status),
        candidate_role_label="INSTRUCTION_APPROVER",
        candidates_evaluated=data.get("candidates_evaluated"),
    )


def _instruction_eligible_empty_message(status: str) -> str:
    if status == "APPROVED":
        return "This instruction is already APPROVED."
    if status in {"REJECTED", "USED", "EXPIRED", "CANCELLED"}:
        return f"This instruction is {status} and cannot be approved."
    return "No users currently satisfy APPROVE policy for this instruction."
