"""Tests for read-only Cypher validation in etl.main."""

from __future__ import annotations

import pytest
from cypher_gen import validate_read_only_cypher


def test_valid_read_query():
    validate_read_only_cypher("MATCH (n) RETURN n LIMIT 10")


def test_valid_query_with_comments_and_strings():
    cypher = """
    // find events
    MATCH (e:SecurityEvent)
    WHERE e.message CONTAINS 'CREATE DROP'
    RETURN e LIMIT 5
    """
    validate_read_only_cypher(cypher)


def test_empty_query_raises():
    with pytest.raises(ValueError, match="empty query"):
        validate_read_only_cypher("   ")


def test_query_too_long_raises():
    long_query = "MATCH (n) RETURN n LIMIT 1" + ("x" * 4090)
    assert len(long_query) > 4096
    with pytest.raises(ValueError, match="4096 characters"):
        validate_read_only_cypher(long_query)


def test_multiple_statements_raises():
    with pytest.raises(ValueError, match="multiple statements"):
        validate_read_only_cypher("MATCH (n) RETURN n LIMIT 1; MATCH (m) RETURN m LIMIT 1")


def test_must_start_with_read_keyword():
    with pytest.raises(ValueError, match="must begin with"):
        validate_read_only_cypher("CREATE (n) RETURN n LIMIT 1")


def test_write_keyword_in_query_raises():
    with pytest.raises(ValueError, match="disallowed write keyword"):
        validate_read_only_cypher("MATCH (n) SET n.x = 1 RETURN n LIMIT 1")


def test_write_procedure_raises():
    with pytest.raises(ValueError, match="write-capable procedure"):
        validate_read_only_cypher(
            "MATCH (n) CALL apoc.periodic.submit('job', 'RETURN 1') YIELD batch RETURN batch LIMIT 1"
        )


def test_missing_limit_raises():
    with pytest.raises(ValueError, match="LIMIT clause"):
        validate_read_only_cypher("MATCH (n) RETURN n")


def test_optional_match_allowed():
    validate_read_only_cypher("OPTIONAL MATCH (n)-[:REL]->(m) RETURN n, m LIMIT 20")


def test_unwind_allowed():
    validate_read_only_cypher("UNWIND [1,2,3] AS x RETURN x LIMIT 3")
