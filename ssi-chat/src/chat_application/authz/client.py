from __future__ import annotations

import logging
from typing import Any

import httpx

from chat_application.auth.service_identity import service_identity
from chat_application.config import settings
from chat_application.formatting import (
    format_eligible_approvers_section,
    format_identity_token,
    format_identity_tokens_in_text,
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
        authorization_service_url: str | None = None,
    ) -> None:
        self._payment_base = (payment_service_url or settings.payment_service_url).rstrip("/")
        self._instruction_base = (
            instruction_service_url or settings.instruction_service_url
        ).rstrip("/")
        self._authorization_base = (
            authorization_service_url or settings.authorization_service_url
        ).rstrip("/")

    async def _compliance_headers(
        self,
        *,
        bearer_token: str,
        session_id: str | None = None,
    ) -> dict[str, str]:
        """Build OBO headers for compliance questions (svc-chat + user JWT)."""
        if not service_identity.token:
            await service_identity.ensure_logged_in()

        svc_token = service_identity.token
        if not svc_token:
            raise EligibilityClientError(
                "chat service identity not logged in — cannot call domain services with OBO"
            )
        headers = {
            "Authorization": f"Bearer {svc_token}",
            "Accept": "application/json",
            "X-On-Behalf-Of": bearer_token,
        }
        if service_identity.session_id:
            headers["X-Session-Id"] = service_identity.session_id
        if session_id:
            headers["X-On-Behalf-Of-Session-Id"] = session_id
        return headers

    async def eligible_approvers_for_payment(
        self,
        payment_id: str,
        *,
        bearer_token: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self._payment_base}/api/v1/payments/{payment_id}/eligible-approvers"
        headers = await self._compliance_headers(
            bearer_token=bearer_token, session_id=session_id
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers)

        if response.status_code == 401:
            raise EligibilityClientError("authentication required — sign in to PolicyPilot")
        if response.status_code == 403:
            detail = response.json().get("detail", response.text)
            raise EligibilityClientError(str(detail) or "not authorized for this question")
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
        headers = await self._compliance_headers(
            bearer_token=bearer_token, session_id=session_id
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers)

        if response.status_code == 401:
            raise EligibilityClientError("authentication required — sign in to PolicyPilot")
        if response.status_code == 403:
            detail = response.json().get("detail", response.text)
            raise EligibilityClientError(str(detail) or "not authorized for this question")
        if response.status_code == 404:
            detail = response.json().get("detail", response.text)
            raise EligibilityClientError(str(detail))
        if not response.is_success:
            detail = response.json().get("detail", response.text)
            raise EligibilityClientError(f"instruction service error: {detail}")

        return response.json()

    async def group_members(
        self,
        group: str,
        *,
        bearer_token: str,
        role: str | None = None,
        covering_lob: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        from urllib.parse import quote

        url = f"{self._authorization_base}/api/v1/authorization/groups/{quote(group, safe='')}/members"
        headers = await self._compliance_headers(
            bearer_token=bearer_token, session_id=session_id
        )

        params: dict[str, str] = {}
        if role:
            params["role"] = role
        if covering_lob:
            params["covering_lob"] = covering_lob

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params or None)

        if response.status_code == 401:
            raise EligibilityClientError("authentication required — sign in to PolicyPilot")
        if response.status_code == 403:
            detail = response.json().get("detail", response.text)
            raise EligibilityClientError(str(detail) or "not authorized for this question")
        if not response.is_success:
            detail = response.json().get("detail", response.text)
            raise EligibilityClientError(f"authorization service error: {detail}")

        return response.json()

    async def person_permission_summary(
        self,
        *,
        query: str,
        bearer_token: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self._authorization_base}/api/v1/authorization/users/permission-summary"
        headers = await self._compliance_headers(
            bearer_token=bearer_token, session_id=session_id
        )

        params = {"q": query}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)

        if response.status_code == 401:
            raise EligibilityClientError("authentication required — sign in to PolicyPilot")
        if response.status_code == 403:
            detail = response.json().get("detail", response.text)
            raise EligibilityClientError(str(detail) or "not authorized for this question")
        if not response.is_success:
            detail = response.json().get("detail", response.text)
            raise EligibilityClientError(f"authorization service error: {detail}")

        return response.json()

    async def payment_amount_limits(
        self,
        *,
        bearer_token: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """OPA club ceilings + absolute limit via authorization-service."""
        url = f"{self._authorization_base}/api/v1/authorization/payment-amount-limits"
        headers = await self._compliance_headers(
            bearer_token=bearer_token, session_id=session_id
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)

        if response.status_code == 401:
            raise EligibilityClientError("authentication required — sign in to PolicyPilot")
        if response.status_code == 403:
            detail = response.json().get("detail", response.text)
            raise EligibilityClientError(str(detail) or "not authorized for this question")
        if not response.is_success:
            detail = response.json().get("detail", response.text)
            raise EligibilityClientError(f"authorization service error: {detail}")

        return response.json()

    async def policy_summary(
        self,
        *,
        domain: str,
        action: str = "APPROVE",
        bearer_token: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self._authorization_base}/api/v1/authorization/policy-summary"
        headers = await self._compliance_headers(
            bearer_token=bearer_token, session_id=session_id
        )

        params = {"domain": domain, "action": action}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)

        if response.status_code == 401:
            raise EligibilityClientError("authentication required — sign in to PolicyPilot")
        if response.status_code == 403:
            detail = response.json().get("detail", response.text)
            raise EligibilityClientError(str(detail) or "not authorized for this question")
        if response.status_code == 404:
            detail = response.json().get("detail", response.text)
            raise EligibilityClientError(str(detail))
        if not response.is_success:
            detail = response.json().get("detail", response.text)
            raise EligibilityClientError(f"authorization service error: {detail}")

        return response.json()


def format_policy_summary_answer(data: dict[str, Any]) -> str:
    title = str(data.get("title") or "Policy summary").strip()
    narrative = str(data.get("narrative") or "").strip()
    domain = str(data.get("domain") or "").strip()
    action = str(data.get("action") or "").strip()
    requires = data.get("requires") or []

    header = f"**{title}**"
    if domain and action:
        header = f"**{title}** (`{domain}` / `{action}`)"

    lines = [header, ""]
    if narrative:
        lines.append(format_identity_tokens_in_text(narrative))
        lines.append("")

    if requires:
        lines.append("Requirements:")
        for item in requires:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "").strip()
            value = str(item.get("value") or "").strip()
            if not kind or not value:
                continue
            lines.append(f"- **{kind}**: {format_identity_token(value)}")
        lines.append("")

    lines.append("_Source: live OPA policy via authorization-service._")
    return "\n".join(lines).strip()


def format_person_permission_summary_answer(data: dict[str, Any]) -> str:
    matches = data.get("matches") or []
    query = str(data.get("query") or "").strip()

    if not matches:
        return (
            f"No users matched `{query}` in the policy directory. "
            "Try a user id (e.g. `pay-203`) or `Family, Given` display name."
        )

    if len(matches) > 1:
        lines = [
            f"Multiple users matched `{query}`. Ask again with a specific user id:",
            "",
        ]
        for row in matches:
            lines.append(
                f"- **{row.get('display_name') or '—'}** (`{row.get('user_id')}`) — "
                f"{row.get('title') or '—'}"
            )
        return "\n".join(lines)

    row = matches[0]
    lines = [
        f"**{row.get('display_name')}** (`{row.get('user_id')}`) — {row.get('title')}",
        "",
    ]
    narrative = str(row.get("narrative") or "").strip()
    if narrative:
        lines.append(format_identity_tokens_in_text(narrative))
        lines.append("")

    roles = ", ".join(format_identity_token(str(r)) for r in (row.get("roles") or [])) or "—"
    groups = ", ".join(format_identity_token(str(g)) for g in (row.get("groups") or [])) or "—"
    clubs = (
        ", ".join(format_identity_token(str(c)) for c in (row.get("amount_clubs") or []))
        or "—"
    )
    covering = ", ".join(row.get("covering_lobs") or []) or "—"
    lob = row.get("lob") or "—"
    lines.extend(
        [
            f"- **roles**: {roles}",
            f"- **groups**: {groups}",
            f"- **amount clubs**: {clubs}",
            f"- **covering LOBs**: {covering}",
            f"- **desk LOB**: {lob}",
            "",
        ]
    )

    capabilities = row.get("capabilities") or []
    if capabilities:
        lines.append("Derived capabilities:")
        for item in capabilities:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "").strip()
            description = str(item.get("description") or "").strip()
            if kind and description:
                lines.append(f"- **{kind}**: {description}")
        lines.append("")

    lines.append(
        "_Source: ZITADEL user directory via authorization-service "
        "(not a live OPA evaluation)._"
    )
    return "\n".join(lines).strip()


def format_group_members_answer(
    data: dict[str, Any],
    *,
    amount: float | None = None,
    covering_lob: str | None = None,
    strict_threshold: bool = True,
) -> str:
    from chat_application.formatting import format_markdown_table, format_usd_compact

    groups = data.get("groups") or []
    if not groups and data.get("group"):
        groups = [str(data["group"])]
    members = data.get("members") or []
    amount_text = format_usd_compact(amount) if amount is not None else None
    lob_note = f" for desk {covering_lob}" if covering_lob else ""
    comparison = "exceeding" if strict_threshold else "of at least"

    if amount_text:
        ceiling_phrase = "above" if strict_threshold else "at or above"
        if len(groups) == 1:
            header = (
                f"Users in {groups[0]} who may approve payments {comparison} {amount_text}{lob_note} "
                f"(policy ceiling lookup — not a live payment evaluation):"
            )
        else:
            club_list = ", ".join(groups)
            header = (
                f"Users who may approve payments {comparison} {amount_text}{lob_note} "
                f"(amount-limit clubs with ceiling {ceiling_phrase} {amount_text}: {club_list}; "
                f"policy ceiling lookup — not a live payment evaluation):"
            )
    elif covering_lob:
        header = (
            f"Users with role FUNDING_APPROVER covering desk {covering_lob} "
            f"(policy directory — not a live payment evaluation):"
        )
    elif len(groups) == 1:
        header = f"Members of {groups[0]}{lob_note} (policy directory):"
    elif groups:
        header = f"Members of {', '.join(groups)}{lob_note} (policy directory):"
    else:
        header = f"Matching users{lob_note} (policy directory):"

    if not members:
        return f"{header}\n\nNo matching users were found."

    table_rows = [
        [
            row.get("user_id") or "—",
            row.get("display_name") or "—",
            row.get("title") or "—",
            ", ".join(row.get("groups") or []) or "—",
            ", ".join(row.get("covering_lobs") or []) or "—",
        ]
        for row in members
    ]
    return (
        f"{header}\n\n"
        f"{format_markdown_table(['User ID', 'Name', 'Title', 'Groups', 'Covering LOBs'], table_rows)}"
    )


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
