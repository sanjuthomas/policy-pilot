from __future__ import annotations

from cypher_gen.extract import extract_cypher


def test_extract_plain_cypher() -> None:
    assert extract_cypher("MATCH (n) RETURN n LIMIT 1") == "MATCH (n) RETURN n LIMIT 1"


def test_extract_from_markdown_fence() -> None:
    raw = """Here is the query:
```cypher
MATCH (e:SecurityEvent)
RETURN e LIMIT 5
```
"""
    assert "SecurityEvent" in extract_cypher(raw)
    assert extract_cypher(raw).startswith("MATCH")


def test_extract_strips_comment_lines() -> None:
    raw = "// header\nMATCH (n) RETURN n LIMIT 1"
    assert extract_cypher(raw) == "MATCH (n) RETURN n LIMIT 1"
