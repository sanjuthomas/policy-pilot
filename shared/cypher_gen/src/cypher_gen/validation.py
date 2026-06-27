from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_LINE_COMMENT = re.compile(r"//[^\n]*", re.MULTILINE)
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_STRING_LITERAL = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")
_WRITE_KEYWORD = re.compile(
    r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DROP|DETACH|FOREACH|LOAD)\b",
    re.IGNORECASE,
)
_WRITE_PROCEDURE = re.compile(
    r"\bCALL\s+(db\.\w+|apoc\.create\.|apoc\.periodic\.|apoc\.merge\.|apoc\.refactor\.)",
    re.IGNORECASE,
)
_READ_START = re.compile(
    r"^\s*(MATCH|OPTIONAL\s+MATCH|WITH|RETURN|UNWIND)\b",
    re.IGNORECASE,
)
_LIMIT_CLAUSE = re.compile(r"\bLIMIT\s+\d+\b", re.IGNORECASE)
_AGGREGATE_RETURN = re.compile(
    r"\bRETURN\b.*\b(count|sum|avg|min|max)\s*\(",
    re.IGNORECASE | re.DOTALL,
)

_MAX_CYPHER_LEN = 4096


def load_graph_schema(schema_path: Path) -> str:
    if schema_path.is_file():
        return schema_path.read_text(encoding="utf-8")
    logger.warning("graph schema file not found: %s", schema_path)
    return ""


def normalize_read_only_cypher(cypher: str) -> str:
    stripped = cypher.strip()
    if not stripped:
        return stripped

    normalized = _LINE_COMMENT.sub("", stripped)
    normalized = _BLOCK_COMMENT.sub("", normalized)
    no_strings = _STRING_LITERAL.sub("''", normalized)

    if _LIMIT_CLAUSE.search(no_strings):
        return stripped
    if _AGGREGATE_RETURN.search(no_strings):
        return stripped.rstrip(";") + "\nLIMIT 1"
    return stripped


def validate_read_only_cypher(cypher: str) -> None:
    stripped = cypher.strip()
    if not stripped:
        raise ValueError("empty query")
    if len(stripped) > _MAX_CYPHER_LEN:
        raise ValueError(f"query exceeds {_MAX_CYPHER_LEN} characters")
    if ";" in stripped.rstrip(";"):
        raise ValueError("multiple statements not allowed")

    normalized = _LINE_COMMENT.sub("", stripped)
    normalized = _BLOCK_COMMENT.sub("", normalized)
    no_strings = _STRING_LITERAL.sub("''", normalized)

    if not _READ_START.match(no_strings):
        raise ValueError(
            "query must begin with MATCH, OPTIONAL MATCH, WITH, RETURN, or UNWIND"
        )
    match = _WRITE_KEYWORD.search(no_strings)
    if match:
        raise ValueError(f"disallowed write keyword '{match.group(0).upper()}'")
    if _WRITE_PROCEDURE.search(no_strings):
        raise ValueError("CALL to a write-capable procedure not allowed")
    if not _LIMIT_CLAUSE.search(no_strings):
        raise ValueError("query must include a LIMIT clause")
