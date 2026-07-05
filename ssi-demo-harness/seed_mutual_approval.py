#!/usr/bin/env python3
"""Seed mutual-approval compliance demo data for chat / Neo4j graph queries.

Question: "Are there any instances of approving each other's instructions?"

The graph pattern (see instruction_mutual_approval in cypher_builder) requires two
users A and B where A approved an instruction B created and B approved an instruction
A created. The current OPA approval matrix does not allow obtaining that symmetry
through policy-allowed approve calls alone, so this script models a collusion scenario
by rewiring CREATED / APPROVED edges on two already-approved FICC instructions.

Usage (from repo root, stack running):

  python3 ssi-demo-harness/seed_mutual_approval.py
  python3 ssi-demo-harness/seed_mutual_approval.py --verify-only

Optional overrides:

  python3 ssi-demo-harness/seed_mutual_approval.py \\
    --user-a ficc-300 --user-b ficc-400 \\
    --instruction-a 20260704-FICC-I-53 --instruction-b 20260704-FICC-I-54
"""

from __future__ import annotations

import argparse
import sys
import time

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "devpassword")

DEFAULT_USER_A = "ficc-300"
DEFAULT_USER_B = "ficc-400"
DEFAULT_INSTRUCTION_A = "20260704-FICC-I-53"
DEFAULT_INSTRUCTION_B = "20260704-FICC-I-54"

MUTUAL_APPROVAL_CHECK = """
MATCH (a:User)-[:APPROVED]->(va:InstructionVersion)<-[:CREATED]-(b:User)
MATCH (b)-[:APPROVED]->(vb:InstructionVersion)<-[:CREATED]-(a)
WHERE a.user_id < b.user_id
RETURN coalesce(a.display_name, a.user_id) AS user_a,
       coalesce(b.display_name, b.user_id) AS user_b,
       va.instruction_id AS a_approved,
       vb.instruction_id AS b_approved
ORDER BY a.user_id, b.user_id
LIMIT 20
"""

REWIRE_PAIR = """
MATCH (v:InstructionVersion {instruction_id: $instruction_id, status: 'APPROVED'})
OPTIONAL MATCH (old_creator:User)-[rc:CREATED]->(v)
OPTIONAL MATCH (old_approver:User)-[ra:APPROVED]->(v)
DELETE rc, ra
WITH v
MERGE (creator:User {user_id: $creator_id})
MERGE (approver:User {user_id: $approver_id})
MERGE (creator)-[:CREATED]->(v)
MERGE (approver)-[:APPROVED]->(v)
SET v.creator_user_id = $creator_id,
    v.approver_user_id = $approver_id
RETURN v.instruction_id AS instruction_id,
       v.version_key AS version_key,
       $creator_id AS creator_id,
       $approver_id AS approver_id
"""


def _load_driver():
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise SystemExit("pip install neo4j") from exc
    return GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)


def _wait_for_approved_version(
    session,
    instruction_id: str,
    *,
    timeout_seconds: float = 30.0,
) -> str | None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        row = session.run(
            """
            MATCH (v:InstructionVersion {instruction_id: $instruction_id, status: 'APPROVED'})
            RETURN v.version_key AS version_key
            LIMIT 1
            """,
            instruction_id=instruction_id,
        ).single()
        if row:
            return row["version_key"]
        time.sleep(1.0)
    return None


def apply_mutual_approval(
    *,
    user_a: str,
    user_b: str,
    instruction_for_b: str,
    instruction_for_a: str,
) -> None:
    """User B created instruction_for_b and user A approved it; vice versa for A."""
    driver = _load_driver()
    with driver.session() as session:
        for instruction_id, creator_id, approver_id in (
            (instruction_for_b, user_b, user_a),
            (instruction_for_a, user_a, user_b),
        ):
            version_key = _wait_for_approved_version(session, instruction_id, timeout_seconds=5.0)
            if not version_key:
                raise SystemExit(
                    f"No APPROVED InstructionVersion found for {instruction_id!r}. "
                    "Run bulk seed or create approved FICC instructions first."
                )
            row = session.run(
                REWIRE_PAIR,
                instruction_id=instruction_id,
                creator_id=creator_id,
                approver_id=approver_id,
            ).single()
            if not row:
                raise SystemExit(f"Failed to rewire {instruction_id}")
            print(
                f"Rewired {row['instruction_id']} ({row['version_key']}): "
                f"creator={row['creator_id']} approver={row['approver_id']}"
            )

        print("\nMutual approval cases in graph:")
        for record in session.run(MUTUAL_APPROVAL_CHECK):
            print(
                f"  {record['user_a']} <-> {record['user_b']}: "
                f"{record['user_a']} approved {record['a_approved']}, "
                f"{record['user_b']} approved {record['b_approved']}"
            )
    driver.close()


def verify_only() -> int:
    driver = _load_driver()
    with driver.session() as session:
        rows = list(session.run(MUTUAL_APPROVAL_CHECK))
    driver.close()
    if not rows:
        print("No mutual approval cases found.")
        return 1
    print(f"Found {len(rows)} mutual approval case(s):")
    for record in rows:
        print(
            f"  {record['user_a']} <-> {record['user_b']}: "
            f"{record['a_approved']} / {record['b_approved']}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-a", default=DEFAULT_USER_A, help="First approver/creator")
    parser.add_argument("--user-b", default=DEFAULT_USER_B, help="Second approver/creator")
    parser.add_argument(
        "--instruction-a",
        default=DEFAULT_INSTRUCTION_A,
        help="Instruction created by user-a and approved by user-b",
    )
    parser.add_argument(
        "--instruction-b",
        default=DEFAULT_INSTRUCTION_B,
        help="Instruction created by user-b and approved by user-a",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only run the mutual-approval Cypher check",
    )
    args = parser.parse_args()

    if args.verify_only:
        return verify_only()

    if args.user_a == args.user_b:
        print("user-a and user-b must differ", file=sys.stderr)
        return 1

    apply_mutual_approval(
        user_a=args.user_a,
        user_b=args.user_b,
        instruction_for_a=args.instruction_a,
        instruction_for_b=args.instruction_b,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
