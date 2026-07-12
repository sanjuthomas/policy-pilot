from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chat_application.models import ChatMessage

_ANAPHORA = re.compile(
    r"\b(those|them|these|the\s+same|that)\b",
    re.IGNORECASE,
)
_LISTISH = re.compile(
    r"\b(list|show|enumerate|display)\b",
    re.IGNORECASE,
)
_PAYMENT_WORD = re.compile(r"\bpayments?\b", re.IGNORECASE)


def expand_follow_up_question(
    message: str,
    history: list[ChatMessage],
) -> str:
    """Attach prior user constraints when the turn is an anaphoric list follow-up.

    Example: after "How many payments did we create this week?", the follow-up
    "Can you list those payments?" becomes a list query that still carries
    "this week" / create semantics from the prior turn so Neo4j planning works.
    """
    text = message.strip()
    if not text or not history:
        return message

    if not _LISTISH.search(text):
        return message
    if not (_ANAPHORA.search(text) or _PAYMENT_WORD.search(text)):
        return message
    # Already self-contained with period filters — keep as-is.
    if re.search(r"\b(today|this\s+week|yesterday)\b", text, re.IGNORECASE) and not _ANAPHORA.search(
        text
    ):
        return message

    prior_user: str | None = None
    for item in reversed(history):
        if item.role == "user" and item.content.strip():
            prior_user = item.content.strip()
            break
    if not prior_user:
        return message
    if not _PAYMENT_WORD.search(prior_user):
        return message
    if prior_user.lower() == text.lower():
        return message

    return f"List the payments matching the prior question: {prior_user}"
