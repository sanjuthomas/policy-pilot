from __future__ import annotations

import re


def extract_cypher(raw: str) -> str:
    text = raw.strip()
    fence = re.search(r"```(?:cypher)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    lines = [line for line in text.splitlines() if not line.strip().startswith("//")]
    return "\n".join(lines).strip()
