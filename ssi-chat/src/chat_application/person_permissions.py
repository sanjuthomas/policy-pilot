from __future__ import annotations

import re

_WHO_LIST = re.compile(r"\b(who|which\s+users?)\b", re.IGNORECASE)

_PERSON_QUERY = re.compile(
    r"(?:"
    r"(?:list|show|summarize|summary|tell\s+me|what\s+are)\s+(?:the\s+)?permissions?\s+(?:of|for)\s+"
    r"|"
    r"permissions?\s+(?:of|for)\s+"
    r"|"
    r"what\s+can\s+"
    r")"
    r"(.+?)"
    r"(?:\s+do\b)?\s*[\?.!]?\s*$",
    re.IGNORECASE,
)

_TRAILING_NOISE = re.compile(
    r"\b(can\s+you|please|could\s+you)\b",
    re.IGNORECASE,
)


def extract_person_permission_query(message: str) -> str | None:
    """Return the person name/id for a person-permission question, else None."""
    text = " ".join(message.strip().split())
    if not text:
        return None
    if _WHO_LIST.search(text):
        return None

    match = _PERSON_QUERY.search(text)
    if not match:
        return None

    person = match.group(1).strip(" \t\"'`")
    person = _TRAILING_NOISE.sub("", person).strip(" ,")
    # Drop leading politeness left in the capture for "Can you list..."
    person = re.sub(
        r"^(?:can\s+you|please|could\s+you)\s+",
        "",
        person,
        flags=re.IGNORECASE,
    ).strip(" ,")
    if len(person) < 2:
        return None
    # Avoid treating policy topics as people.
    if re.search(r"\b(policy|approval|funding|payment|instruction)\b", person, re.IGNORECASE):
        return None
    return person
