from __future__ import annotations

import re

# Normative policy catalog questions (not who-lists / live eligibility).
_WHO_LIST_PATTERN = re.compile(
    r"\b(who|which\s+users?|list|members?)\b",
    re.IGNORECASE,
)

_POLICY_CUE = re.compile(
    r"\b(polic(?:y|ies)|how\s+does|how\s+do|explain|summarize|summary|tell\s+me)\b",
    re.IGNORECASE,
)

_FUNDING_CUE = re.compile(
    r"\b(funding\s+approval|payment\s+approval|approve\s+payments?)\b",
    re.IGNORECASE,
)

_INSTRUCTION_CUE = re.compile(
    r"\b(instruction\s+approval|approve\s+instructions?)\b",
    re.IGNORECASE,
)

_ACTION_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bcreat(?:e|ion|ing)\b", re.IGNORECASE), "CREATE"),
    (re.compile(r"\bsubmit(?:ting|sion)?\b", re.IGNORECASE), "SUBMIT"),
    (re.compile(r"\breject(?:ion|ing)?\b", re.IGNORECASE), "REJECT"),
    (re.compile(r"\bcancel(?:lation|ing)?\b", re.IGNORECASE), "CANCEL"),
    (re.compile(r"\bsuspend(?:sion|ing)?\b", re.IGNORECASE), "SUSPEND"),
    (re.compile(r"\breactivat(?:e|ion|ing)\b", re.IGNORECASE), "REACTIVATE"),
    (re.compile(r"\bupdat(?:e|ing)\b", re.IGNORECASE), "UPDATE"),
    (re.compile(r"\bapprov\w*\b", re.IGNORECASE), "APPROVE"),
)

_POLICIES_MODE_GUIDANCE = (
    "Policies mode answers live OPA / directory questions, for example:\n"
    "- What is the funding approval policy?\n"
    "- What is the instruction approval policy?\n"
    "- Who has permission to approve payments worth more than $25 billion?\n"
    "- Who has permission to approve payments for LOB FICC?\n"
    "- Can you list the permissions of Kowalski, Anna?\n"
    "- Who can approve payment `<payment-id>`?\n"
    "- Who can approve instruction `<instruction-id>`?\n\n"
    "Switch to Security Events, Instructions, or Payments for audit and graph questions."
)


def policies_mode_guidance() -> str:
    return _POLICIES_MODE_GUIDANCE


def _infer_domain(text: str) -> str | None:
    if _FUNDING_CUE.search(text) or (
        re.search(r"\bpayment\b", text, re.IGNORECASE)
        and re.search(r"\bapprov\w*\b", text, re.IGNORECASE)
    ):
        return "payment"
    if _INSTRUCTION_CUE.search(text) or (
        re.search(r"\binstruction\b", text, re.IGNORECASE)
        and re.search(r"\bapprov\w*\b", text, re.IGNORECASE)
    ):
        return "instruction"
    if re.search(r"\bfunding\b", text, re.IGNORECASE):
        return "payment"
    if re.search(r"\bpayment\b", text, re.IGNORECASE) and re.search(
        r"\bpolic(?:y|ies)\b", text, re.IGNORECASE
    ):
        return "payment"
    if re.search(r"\binstruction\b", text, re.IGNORECASE) and re.search(
        r"\bpolic(?:y|ies)\b", text, re.IGNORECASE
    ):
        return "instruction"
    if re.search(r"\bpayment\b", text, re.IGNORECASE):
        return "payment"
    if re.search(r"\binstruction\b", text, re.IGNORECASE):
        return "instruction"
    return None


def _infer_action(text: str) -> str:
    action = "APPROVE"
    for pattern, resolved in _ACTION_ALIASES:
        if pattern.search(text):
            return resolved
    return action


def detect_policy_summary_question(
    message: str,
    *,
    mode: str | None = None,
) -> tuple[str, str] | None:
    """Return ``(domain, action)`` for normative policy-summary questions."""
    text = message.strip()
    if not text:
        return None
    if _WHO_LIST_PATTERN.search(text):
        return None

    policies_mode = mode == "policies"
    if not policies_mode and not _POLICY_CUE.search(text):
        return None

    domain = _infer_domain(text)
    if domain is None:
        if policies_mode and (
            _POLICY_CUE.search(text) or re.search(r"\bapprov\w*\b", text, re.IGNORECASE)
        ):
            # In Policies mode, bare "approval policy" defaults to funding APPROVE.
            domain = "payment"
        else:
            return None

    return domain, _infer_action(text)
