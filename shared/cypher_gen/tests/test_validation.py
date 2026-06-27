from __future__ import annotations

from pathlib import Path

import pytest

from cypher_gen.validation import (
    load_graph_schema,
    normalize_read_only_cypher,
    validate_read_only_cypher,
)


def test_valid_read_query() -> None:
    validate_read_only_cypher("MATCH (n) RETURN n LIMIT 10")


def test_empty_query_raises() -> None:
    with pytest.raises(ValueError, match="empty query"):
        validate_read_only_cypher("   ")


def test_write_keyword_raises() -> None:
    with pytest.raises(ValueError, match="disallowed write keyword"):
        validate_read_only_cypher("MATCH (n) SET n.x = 1 RETURN n LIMIT 1")


def test_missing_limit_raises() -> None:
    with pytest.raises(ValueError, match="LIMIT clause"):
        validate_read_only_cypher("MATCH (n) RETURN n")


def test_normalize_adds_limit_for_aggregate() -> None:
    cypher = "MATCH (n) RETURN count(n) AS total"
    normalized = normalize_read_only_cypher(cypher)
    assert normalized.endswith("LIMIT 1")


def test_normalize_preserves_existing_limit() -> None:
    cypher = "MATCH (n) RETURN n LIMIT 5"
    assert normalize_read_only_cypher(cypher) == cypher


def test_load_graph_schema_from_file(tmp_path: Path) -> None:
    schema_file = tmp_path / "schema.cypher"
    schema_file.write_text("CREATE CONSTRAINT", encoding="utf-8")
    assert load_graph_schema(schema_file) == "CREATE CONSTRAINT"


def test_load_graph_schema_missing_returns_empty(tmp_path: Path) -> None:
    assert load_graph_schema(tmp_path / "missing.cypher") == ""
