#!/usr/bin/env python3
"""Seed cross-entity reciprocal approval demo data for chat / Neo4j graph queries.

Question: "Are there cases where one user created an instruction that another user
approved, and that approver later created a payment on the same instruction that the
original creator then approved?"

Graph pattern (see cross_entity_reciprocal_approval in cypher_builder) on one
instruction + payment pair:

  User A — created instruction, approved payment
  User B — approved instruction, created payment

OPA cannot produce this through allowed API calls alone:

  • Instruction creators/approvers use desk IDs (mo-*, ficc-*, fx-*).
  • Payment creators/approvers use middle-office IDs (pay-*).
  • No seed user holds both INSTRUCTION_CREATOR and PAYMENT_CREATOR (or the
    symmetric approver roles) needed to swap roles across entity types.

Like seed_mutual_approval.py, this script rewires CREATED / APPROVED edges and
version properties on an already-approved instruction and payment on the same route.

Usage (from repo root, stack running):

  python3 ssi-demo-harness/seed_cross_entity_reciprocal.py
  python3 ssi-demo-harness/seed_cross_entity_reciprocal.py --verify-only

Optional overrides:

  python3 ssi-demo-harness/seed_cross_entity_reciprocal.py \\
    --user-a pay-102 --user-b pay-201 \\
    --instruction-id 20260705-FICC-I-8 --payment-id 20260705-FICC-P-9
"""

from __future__ import annotations

import argparse
import sys
import time

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "devpassword")

DEFAULT_USER_A = "pay-102"
DEFAULT_USER_B = "pay-201"
DEFAULT_INSTRUCTION_ID = "20260705-FICC-I-8"
DEFAULT_PAYMENT_ID = "20260705-FICC-P-9"

CROSS_ENTITY_CHECK = """
MATCH (i:Instruction)-[:CURRENT]->(iv:InstructionVersion)
MATCH (i)-[:HAS_PAYMENT]->(pay:Payment)-[:CURRENT]->(pv:PaymentVersion)
WHERE iv.creator_user_id IS NOT NULL
  AND iv.approver_user_id IS NOT NULL
  AND pv.creator_user_id IS NOT NULL
  AND pv.approver_user_id IS NOT NULL
  AND iv.creator_user_id = pv.approver_user_id
  AND iv.approver_user_id = pv.creator_user_id
  AND iv.creator_user_id <> iv.approver_user_id
OPTIONAL MATCH (instr_creator:User {user_id: iv.creator_user_id})
OPTIONAL MATCH (instr_approver:User {user_id: iv.approver_user_id})
OPTIONAL MATCH (pay_creator:User {user_id: pv.creator_user_id})
OPTIONAL MATCH (pay_approver:User {user_id: pv.approver_user_id})
RETURN i.instruction_id AS instruction_id,
       pay.payment_id AS payment_id,
       coalesce(instr_creator.display_name, iv.creator_user_id) AS instruction_creator,
       coalesce(instr_approver.display_name, iv.approver_user_id) AS instruction_approver,
       coalesce(pay_creator.display_name, pv.creator_user_id) AS payment_creator,
       coalesce(pay_approver.display_name, pv.approver_user_id) AS payment_approver
ORDER BY instruction_id, payment_id
LIMIT 20
"""

REWIRE_INSTRUCTION = """
MATCH (v:InstructionVersion {instruction_id: $instruction_id, status: 'APPROVED'})
OPTIONAL MATCH (old_creator:User)-[rc:CREATED_IV]->(v)
OPTIONAL MATCH (old_approver:User)-[ra:APPROVED_IV]->(v)
DELETE rc, ra
WITH v
MERGE (creator:User {user_id: $creator_id})
MERGE (approver:User {user_id: $approver_id})
MERGE (creator)-[:CREATED_IV]->(v)
MERGE (approver)-[:APPROVED_IV]->(v)
SET v.creator_user_id = $creator_id,
    v.approver_user_id = $approver_id
RETURN v.instruction_id AS instruction_id,
       v.version_key AS version_key,
       $creator_id AS creator_id,
       $approver_id AS approver_id
"""

REWIRE_PAYMENT = """
MATCH (pv:PaymentVersion {payment_id: $payment_id, status: 'APPROVED'})
OPTIONAL MATCH (old_creator:User)-[rc:CREATED_PV]->(pv)
OPTIONAL MATCH (old_approver:User)-[ra:APPROVED_PV]->(pv)
DELETE rc, ra
WITH pv
MERGE (creator:User {user_id: $creator_id})
MERGE (approver:User {user_id: $approver_id})
MERGE (creator)-[:CREATED_PV]->(pv)
MERGE (approver)-[:APPROVED_PV]->(pv)
SET pv.creator_user_id = $creator_id,
    pv.approver_user_id = $approver_id
RETURN pv.payment_id AS payment_id,
       pv.version_key AS version_key,
       $creator_id AS creator_id,
       $approver_id AS approver_id
"""


def _load_driver():
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise SystemExit("pip install neo4j") from exc
    return GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)


def _wait_for_row(
    session,
    cypher: str,
    *,
    params: dict,
    timeout_seconds: float = 30.0,
) -> dict | None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        row = session.run(cypher, **params).single()
        if row:
            return dict(row)
        time.sleep(1.0)
    return None


def _assert_linked_route(session, instruction_id: str, payment_id: str) -> None:
    row = session.run(
        """
        MATCH (i:Instruction {instruction_id: $instruction_id})-[:HAS_PAYMENT]->(p:Payment {payment_id: $payment_id})
        RETURN i.instruction_id AS instruction_id, p.payment_id AS payment_id
        """,
        instruction_id=instruction_id,
        payment_id=payment_id,
    ).single()
    if not row:
        raise SystemExit(
            f"Payment {payment_id!r} is not linked to instruction {instruction_id!r}. "
            "Pick a pair from the same instruction route."
        )


def apply_cross_entity_reciprocal(
    *,
    user_a: str,
    user_b: str,
    instruction_id: str,
    payment_id: str,
) -> None:
    """User A created instruction / approved payment; user B approved / created payment."""
    driver = _load_driver()
    with driver.session() as session:
        _assert_linked_route(session, instruction_id, payment_id)

        iv = _wait_for_row(
            session,
            """
            MATCH (v:InstructionVersion {instruction_id: $instruction_id, status: 'APPROVED'})
            RETURN v.version_key AS version_key
            LIMIT 1
            """,
            params={"instruction_id": instruction_id},
            timeout_seconds=5.0,
        )
        if not iv:
            raise SystemExit(
                f"No APPROVED InstructionVersion found for {instruction_id!r}. "
                "Run bulk seed or create approved instructions first."
            )

        pv = _wait_for_row(
            session,
            """
            MATCH (v:PaymentVersion {payment_id: $payment_id, status: 'APPROVED'})
            RETURN v.version_key AS version_key
            LIMIT 1
            """,
            params={"payment_id": payment_id},
            timeout_seconds=5.0,
        )
        if not pv:
            raise SystemExit(
                f"No APPROVED PaymentVersion found for {payment_id!r}. "
                "Approve a payment on the chosen instruction first."
            )

        instr_row = session.run(
            REWIRE_INSTRUCTION,
            instruction_id=instruction_id,
            creator_id=user_a,
            approver_id=user_b,
        ).single()
        if not instr_row:
            raise SystemExit(f"Failed to rewire instruction {instruction_id}")
        print(
            f"Rewired instruction {instr_row['instruction_id']} ({instr_row['version_key']}): "
            f"creator={instr_row['creator_id']} approver={instr_row['approver_id']}"
        )

        pay_row = session.run(
            REWIRE_PAYMENT,
            payment_id=payment_id,
            creator_id=user_b,
            approver_id=user_a,
        ).single()
        if not pay_row:
            raise SystemExit(f"Failed to rewire payment {payment_id}")
        print(
            f"Rewired payment {pay_row['payment_id']} ({pay_row['version_key']}): "
            f"creator={pay_row['creator_id']} approver={pay_row['approver_id']}"
        )

        print("\nCross-entity reciprocal approval cases in graph:")
        rows = list(session.run(CROSS_ENTITY_CHECK))
        if not rows:
            print("  (none — rewire may not have persisted)")
            return
        for record in rows:
            print(
                f"  {record['instruction_id']} / {record['payment_id']}: "
                f"instr creator={record['instruction_creator']}, "
                f"instr approver={record['instruction_approver']}, "
                f"pay creator={record['payment_creator']}, "
                f"pay approver={record['payment_approver']}"
            )
    driver.close()


def verify_only() -> int:
    driver = _load_driver()
    with driver.session() as session:
        rows = list(session.run(CROSS_ENTITY_CHECK))
    driver.close()
    if not rows:
        print("No cross-entity reciprocal approval cases found.")
        return 1
    print(f"Found {len(rows)} cross-entity reciprocal approval case(s):")
    for record in rows:
        print(
            f"  {record['instruction_id']} / {record['payment_id']}: "
            f"{record['instruction_creator']} -> {record['instruction_approver']} / "
            f"{record['payment_creator']} -> {record['payment_approver']}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user-a",
        default=DEFAULT_USER_A,
        help="Instruction creator and payment approver",
    )
    parser.add_argument(
        "--user-b",
        default=DEFAULT_USER_B,
        help="Instruction approver and payment creator",
    )
    parser.add_argument("--instruction-id", default=DEFAULT_INSTRUCTION_ID)
    parser.add_argument("--payment-id", default=DEFAULT_PAYMENT_ID)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only run the cross-entity reciprocal Cypher check",
    )
    args = parser.parse_args()

    if args.verify_only:
        return verify_only()

    if args.user_a == args.user_b:
        print("user-a and user-b must differ", file=sys.stderr)
        return 1

    apply_cross_entity_reciprocal(
        user_a=args.user_a,
        user_b=args.user_b,
        instruction_id=args.instruction_id,
        payment_id=args.payment_id,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
