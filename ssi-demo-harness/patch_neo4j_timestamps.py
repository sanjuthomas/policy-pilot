#!/usr/bin/env python3
"""Backdate InstructionVersion / PaymentVersion timestamps in Neo4j from bulk seed manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BATCH = 100
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "devpassword")


def _load_driver():
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise SystemExit("pip install neo4j") from exc
    return GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)


def _chunks(items: list, size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]


def patch_instructions(session, rows: list[dict]) -> None:
    query = """
    UNWIND $rows AS row
    MATCH (v:InstructionVersion {instruction_id: row.instruction_id})
    SET v.timestamp = row.created_at,
        v.updated_at = row.created_at
    """
    session.run(query, rows=rows)


def patch_payments(session, rows: list[dict]) -> None:
    query = """
    UNWIND $rows AS row
    MATCH (v:PaymentVersion {payment_id: row.payment_id})
    SET v.created_at = row.created_at,
        v.updated_at = row.created_at,
        v.timestamp = row.created_at,
        v.value_date = row.value_date
    """
    session.run(query, rows=rows)


def main() -> int:
    manifest_path = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/bulk_seed_timestamps.json")
    if not manifest_path.is_file():
        print(f"manifest not found: {manifest_path}", file=sys.stderr)
        return 1

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    instructions = payload.get("instructions", [])
    payments = payload.get("payments", [])
    print(f"Patching Neo4j: {len(instructions)} instructions, {len(payments)} payments")

    driver = _load_driver()
    with driver.session() as session:
        for batch in _chunks(instructions, BATCH):
            patch_instructions(session, batch)
        for batch in _chunks(payments, BATCH):
            patch_payments(session, batch)
    driver.close()
    print("Neo4j timestamp patch complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
