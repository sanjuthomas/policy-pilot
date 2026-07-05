from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

from etl.authorization_context import (
    authorization_fact_neo4j_params,
    authorization_neo4j_params,
)
from etl.config import settings
from etl.enrichment import EnrichedSecurityEventDocument
from etl.graph_model import (
    INSTRUCTION_ACTION_TO_EDGE,
    PAYMENT_ACTION_TO_EDGE,
    instruction_lifecycle_actor,
    is_version_open,
    payment_lifecycle_actor,
    release_use_payment_id,
)
from etl.multimodal_write import MultimodalWrite, upsert_multimodal_writes_in_tx

logger = logging.getLogger(__name__)


def _roles_json(roles: list | None) -> str | None:
    if not roles:
        return None
    return json.dumps(roles)


def _instruction_version_key(instruction_id: str, version_number: int) -> str:
    return f"{instruction_id}:{version_number}"


def _payment_version_key(payment_id: str, version_number: int) -> str:
    return f"{payment_id}:{version_number}"


def _payment_version_number(payload: dict[str, Any]) -> int:
    snap = payload.get("payment_snapshot") or {}
    if snap.get("version_number") is not None:
        return int(snap["version_number"])
    if payload.get("version_number") is not None:
        return int(payload["version_number"])
    lifecycle = snap.get("lifecycle_events") or payload.get("lifecycle_events") or []
    if lifecycle:
        return len(lifecycle)
    return 1


def _user_merge_params(prefix: str, user: dict[str, Any]) -> dict[str, Any]:
    return {
        f"{prefix}_given_name": user.get("given_name"),
        f"{prefix}_family_name": user.get("family_name"),
        f"{prefix}_title": user.get("title"),
        f"{prefix}_lob": user.get("lob"),
        f"{prefix}_roles": _roles_json(user.get("roles")),
        f"{prefix}_supervisor_id": user.get("supervisor_id"),
    }


class Neo4jGraphWriter:
    def __init__(self) -> None:
        self._driver: AsyncDriver | None = None
        self._schema_applied = False

    async def connect(self) -> None:
        self._driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        await self._driver.verify_connectivity()
        await self._apply_schema()
        logger.info("Neo4j graph writer connected")

    async def close(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    async def _apply_schema(self) -> None:
        if self._schema_applied or self._driver is None:
            return

        schema_path = Path(settings.graph_model_dir) / "schema.cypher"
        if not schema_path.is_file():
            logger.warning("Neo4j schema file not found: %s", schema_path)
            return

        statements = [
            chunk.strip()
            for chunk in schema_path.read_text(encoding="utf-8").split(";")
            if chunk.strip() and not chunk.strip().startswith("//")
        ]
        async with self._driver.session() as session:
            for statement in statements:
                try:
                    await session.run(statement)
                except Exception as exc:
                    logger.warning("Neo4j schema statement failed: %s | %s", exc, statement[:120])
        self._schema_applied = True
        logger.info("applied %s Neo4j schema statement(s)", len(statements))

    async def upsert(
        self,
        document: EnrichedSecurityEventDocument,
        *,
        multimodal: MultimodalWrite | None = None,
        extra_multimodal: list[MultimodalWrite] | None = None,
    ) -> None:
        if self._driver is None:
            raise RuntimeError("Neo4j writer not connected")

        event = document.security_event
        actor = event.get("actor") or {}
        resource = event.get("resource") or {}
        event_ctx = event.get("event") or {}
        source = event.get("source") or {}
        merged = document.merged or {}
        instruction = document.instruction or {}
        approved_by = instruction.get("approved_by") or {}

        version_number = document.version_number or instruction.get("version_number")
        version_key = (
            _instruction_version_key(document.instruction_id, version_number)
            if document.instruction_id and version_number is not None
            else None
        )

        owning_lob = merged.get("owning_lob") or resource.get("owning_lob")
        wire_scope = merged.get("wire_scope")
        instruction_type = merged.get("instruction_type")
        currency = merged.get("currency")
        action = event_ctx.get("action")
        outcome = event_ctx.get("outcome")
        auth_params = authorization_neo4j_params(event)

        # All writes in a single transaction for atomicity
        async with self._driver.session() as session:
            tx = await session.begin_transaction()
            try:

                # --- SecurityEvent node ---
                await tx.run(
                    """
                    MERGE (e:SecurityEvent {event_id: $event_id})
                    SET e.timestamp        = $timestamp,
                        e.severity         = $severity,
                        e.message          = $message,
                        e.action           = $action,
                        e.outcome          = $outcome,
                        e.reason           = $reason,
                        e.event_type       = $event_type,
                        e.source_application = $source_application,
                        e.source_version   = $source_version,
                        e.wire_scope       = $wire_scope,
                        e.instruction_type = $instruction_type,
                        e.owning_lob       = $owning_lob,
                        e.authorization_summary = $authorization_summary,
                        e.authorization_decision = $authorization_decision,
                        e.authorization_basis = $authorization_basis,
                        e.authorization_violations = $authorization_violations
                    """,
                    event_id=document.event_id,
                    timestamp=event.get("timestamp"),
                    severity=event.get("severity"),
                    message=event.get("message"),
                    action=action,
                    outcome=outcome,
                    reason=event_ctx.get("reason"),
                    event_type=json.dumps(event.get("event_type") or []),
                    source_application=source.get("application"),
                    source_version=source.get("version"),
                    wire_scope=wire_scope,
                    instruction_type=instruction_type,
                    owning_lob=owning_lob,
                    **auth_params,
                )

                # --- Actor User node + ACTED_AS + BELONGS_TO ---
                if actor.get("user_id"):
                    await tx.run(
                        """
                        MERGE (u:User {user_id: $user_id})
                        SET u.given_name    = coalesce($given_name, u.given_name),
                            u.family_name   = coalesce($family_name, u.family_name),
                            u.display_name  = coalesce(
                                CASE WHEN $family_name IS NOT NULL AND $given_name IS NOT NULL
                                     THEN $family_name + ', ' + $given_name + ' (' + $user_id + ')'
                                     ELSE null END,
                                u.display_name),
                            u.title         = coalesce($title, u.title),
                            u.lob           = coalesce($lob, u.lob),
                            u.roles         = coalesce($roles, u.roles),
                            u.supervisor_id = coalesce($supervisor_id, u.supervisor_id)
                        WITH u
                        MATCH (e:SecurityEvent {event_id: $event_id})
                        MERGE (u)-[:ACTED_AS]->(e)
                        WITH u
                        WHERE u.lob IS NOT NULL
                        MERGE (p:ProfitCenter {lob: u.lob})
                        MERGE (u)-[:BELONGS_TO]->(p)
                        """,
                        user_id=actor["user_id"],
                        given_name=actor.get("given_name"),
                        family_name=actor.get("family_name"),
                        title=actor.get("title"),
                        lob=actor.get("lob"),
                        roles=_roles_json(actor.get("roles")),
                        supervisor_id=actor.get("supervisor_id"),
                        event_id=document.event_id,
                    )

                    # REPORTS_TO for actor
                    if actor.get("supervisor_id"):
                        await tx.run(
                            """
                            MERGE (u:User {user_id: $user_id})
                            MERGE (s:User {user_id: $supervisor_id})
                            MERGE (u)-[:REPORTS_TO]->(s)
                            """,
                            user_id=actor["user_id"],
                            supervisor_id=actor["supervisor_id"],
                        )

                # --- InstructionVersion (sparse merge for search) + FOR ---
                if version_key and document.instruction_id:
                    end_date = merged.get("end_date")
                    await tx.run(
                        """
                        MERGE (i:Instruction {instruction_id: $instruction_id})
                        MERGE (v:InstructionVersion {version_key: $version_key})
                        SET v.instruction_id      = $instruction_id,
                            v.version_number      = $version_number,
                            v.status              = $status,
                            v.instruction_type    = $instruction_type,
                            v.wire_scope          = $wire_scope,
                            v.owning_lob          = $owning_lob,
                            v.currency            = $currency,
                            v.effective_date      = $effective_date,
                            v.end_date            = $end_date,
                            v.usage_count         = $usage_count,
                            v.creator_user_id     = $creator_user_id,
                            v.approver_user_id    = $approver_user_id,
                            v.rejector_user_id    = $rejector_user_id,
                            v.creditor_name       = $creditor_name,
                            v.creditor_account_id = $creditor_account_id,
                            v.debtor_name         = $debtor_name,
                            v.debtor_account_id   = $debtor_account_id,
                            v.creditor_agent_bic  = $creditor_agent_bic,
                            v.is_expired          = CASE
                                WHEN $end_date IS NOT NULL AND datetime($end_date) < datetime()
                                THEN true ELSE false END
                        MERGE (i)-[:HAS_VERSION]->(v)
                        """,
                        instruction_id=document.instruction_id,
                        version_key=version_key,
                        version_number=version_number,
                        status=merged.get("status") or instruction.get("status"),
                        instruction_type=instruction_type,
                        wire_scope=wire_scope,
                        owning_lob=owning_lob,
                        currency=currency,
                        effective_date=merged.get("effective_date"),
                        end_date=end_date,
                        usage_count=merged.get("usage_count"),
                        creator_user_id=merged.get("creator_user_id"),
                        approver_user_id=merged.get("approver_user_id"),
                        rejector_user_id=merged.get("rejector_user_id"),
                        creditor_name=merged.get("creditor_name"),
                        creditor_account_id=merged.get("creditor_account_id"),
                        debtor_name=merged.get("debtor_name"),
                        debtor_account_id=merged.get("debtor_account_id"),
                        creditor_agent_bic=merged.get("creditor_agent_bic"),
                    )

                    await tx.run(
                        """
                        MATCH (e:SecurityEvent {event_id: $event_id})
                        MATCH (v:InstructionVersion {version_key: $version_key})
                        MERGE (e)-[:FOR]->(v)
                        """,
                        event_id=document.event_id,
                        version_key=version_key,
                    )

                    if action == "APPROVE" and outcome == "success":
                        await tx.run(
                            """
                            MATCH (v:InstructionVersion {version_key: $version_key})
                            SET v.approved_at = coalesce($approved_at, v.approved_at),
                                v.approver_user_id = coalesce($approver_user_id, v.approver_user_id),
                                v.authorization_summary = coalesce(
                                    $authorization_summary, v.authorization_summary
                                ),
                                v.authorization_basis = coalesce(
                                    $authorization_basis, v.authorization_basis
                                )
                            """,
                            version_key=version_key,
                            approved_at=instruction.get("approved_at") or event.get("timestamp"),
                            approver_user_id=approved_by.get("user_id") or actor.get("user_id"),
                            authorization_summary=auth_params.get("authorization_summary"),
                            authorization_basis=auth_params.get("authorization_basis"),
                        )

                # --- SecurityEvent → ProfitCenter (INVOLVES_LOB) ---
                if owning_lob:
                    await tx.run(
                        """
                        MATCH (e:SecurityEvent {event_id: $event_id})
                        MERGE (p:ProfitCenter {lob: $owning_lob})
                        MERGE (e)-[:INVOLVES_LOB]->(p)
                        """,
                        event_id=document.event_id,
                        owning_lob=owning_lob,
                    )

                await upsert_multimodal_writes_in_tx(tx, multimodal, extra_multimodal)
                await tx.commit()
            except Exception:
                await tx.rollback()
                raise

    async def graph_stats(self) -> dict[str, int]:
        if self._driver is None:
            raise RuntimeError("Neo4j writer not connected")

        query = """
        MATCH (n)
        UNWIND labels(n) AS label
        RETURN label, count(*) AS count
        ORDER BY count DESC
        """
        stats: dict[str, int] = {}
        async with self._driver.session() as session:
            result = await session.run(query)
            async for record in result:
                stats[str(record["label"])] = int(record["count"])
        return stats

    async def search_events(
        self,
        *,
        text: str = "",
        action: str = "",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if self._driver is None:
            raise RuntimeError("Neo4j writer not connected")

        query = """
        MATCH (e:SecurityEvent)
        WHERE ($text = ''
               OR toLower(coalesce(e.message, '')) CONTAINS toLower($text)
               OR toLower(coalesce(e.action, '')) CONTAINS toLower($text))
          AND ($action = '' OR e.action = $action)
        RETURN e
        ORDER BY e.timestamp DESC
        LIMIT $limit
        """
        events: list[dict[str, Any]] = []
        async with self._driver.session() as session:
            result = await session.run(query, text=text, action=action, limit=limit)
            async for record in result:
                events.append(dict(record["e"]))
        return events

    async def get_event_subgraph(self, event_id: str) -> dict[str, Any] | None:
        if self._driver is None:
            raise RuntimeError("Neo4j writer not connected")

        query = """
        MATCH (e:SecurityEvent {event_id: $event_id})
        OPTIONAL MATCH (actor:User)-[:ACTED_AS]->(e)
        OPTIONAL MATCH (e)-[:FOR]->(v:InstructionVersion)
        OPTIONAL MATCH (i:Instruction {instruction_id: v.instruction_id})
        OPTIONAL MATCH (e)-[:INVOLVES_LOB]->(p:ProfitCenter)
        RETURN e,
               collect(DISTINCT actor)    AS actors,
               i,
               v,
               p
        """
        async with self._driver.session() as session:
            result = await session.run(query, event_id=event_id)
            record = await result.single()
            if record is None or record["e"] is None:
                return None

            return {
                "event":      dict(record["e"]),
                "actors":     [dict(n) for n in record["actors"]    if n],
                "instruction": dict(record["i"]) if record["i"]     else None,
                "version":    dict(record["v"]) if record["v"]      else None,
                "profit_center": dict(record["p"]) if record["p"]   else None,
            }

    async def get_instruction_subgraph(self, instruction_id: str) -> dict[str, Any] | None:
        if self._driver is None:
            raise RuntimeError("Neo4j writer not connected")

        query = """
        MATCH (i:Instruction {instruction_id: $instruction_id})
        OPTIONAL MATCH (i)-[:HAS_VERSION]->(v:InstructionVersion)
        OPTIONAL MATCH (e:SecurityEvent)-[:FOR]->(v)
        RETURN i,
               collect(DISTINCT v)        AS versions,
               collect(DISTINCT e)        AS events
        """
        async with self._driver.session() as session:
            result = await session.run(query, instruction_id=instruction_id)
            record = await result.single()
            if record is None or record["i"] is None:
                return None

            return {
                "instruction": dict(record["i"]),
                "versions":  [dict(n) for n in record["versions"]  if n],
                "events":    [dict(n) for n in record["events"]    if n],
            }

    async def _write_lifecycle_edge(
        self,
        tx: Any,
        *,
        edge_type: str,
        user_id: str,
        version_key: str,
        at: str | None,
        extra_props: dict[str, Any] | None = None,
        user_params: dict[str, Any] | None = None,
    ) -> None:
        props = {"at": at, **(extra_props or {})}
        user_params = user_params or {}
        set_clause = ", ".join(f"r.{key} = ${key}" for key in props) or "r.at = coalesce(r.at, $at)"
        await tx.run(
            f"""
            MERGE (u:User {{user_id: $user_id}})
            SET   u.given_name    = coalesce($given_name, u.given_name),
                  u.family_name   = coalesce($family_name, u.family_name),
                  u.display_name  = coalesce(
                      CASE WHEN $family_name IS NOT NULL AND $given_name IS NOT NULL
                           THEN $family_name + ', ' + $given_name + ' (' + $user_id + ')'
                           ELSE null END,
                      u.display_name),
                  u.title         = coalesce($title, u.title),
                  u.lob           = coalesce($lob, u.lob),
                  u.roles         = coalesce($roles, u.roles),
                  u.supervisor_id = coalesce($supervisor_id, u.supervisor_id)
            WITH u
            MATCH (v:InstructionVersion {{version_key: $version_key}})
            MERGE (u)-[r:{edge_type}]->(v)
            SET {set_clause}
            """,
            user_id=user_id,
            version_key=version_key,
            given_name=user_params.get("given_name"),
            family_name=user_params.get("family_name"),
            title=user_params.get("title"),
            lob=user_params.get("lob"),
            roles=user_params.get("roles"),
            supervisor_id=user_params.get("supervisor_id"),
            **props,
        )

    def _instruction_lifecycle_user_params(
        self,
        fact: dict[str, Any],
        user_id: str,
    ) -> dict[str, Any]:
        if fact.get("actor_user_id") == user_id:
            return {
                "given_name": fact.get("actor_given_name"),
                "family_name": fact.get("actor_family_name"),
                "title": fact.get("actor_title"),
                "lob": fact.get("actor_lob"),
                "roles": _roles_json(fact.get("actor_roles")),
                "supervisor_id": fact.get("actor_supervisor_id"),
            }
        snap = fact.get("instruction_snapshot") or {}
        for key, prefix in (
            ("created_by", "creator"),
            ("approved_by", "approver"),
            ("rejected_by", "rejector"),
        ):
            user = snap.get(key) or {}
            if user.get("user_id") == user_id:
                params = _user_merge_params(prefix, user)
                return {
                    "given_name": params[f"{prefix}_given_name"],
                    "family_name": params[f"{prefix}_family_name"],
                    "title": params[f"{prefix}_title"],
                    "lob": params[f"{prefix}_lob"],
                    "roles": params[f"{prefix}_roles"],
                    "supervisor_id": params[f"{prefix}_supervisor_id"],
                }
        return {}

    def _payment_lifecycle_user_params(
        self,
        fact: dict[str, Any],
        user_id: str,
    ) -> dict[str, Any]:
        if fact.get("actor_user_id") == user_id:
            return {
                "given_name": fact.get("actor_given_name"),
                "family_name": fact.get("actor_family_name"),
                "title": fact.get("actor_title"),
                "lob": fact.get("actor_lob"),
                "roles": _roles_json(fact.get("actor_roles")),
                "supervisor_id": fact.get("actor_supervisor_id"),
            }
        for key, prefix in (
            ("created_by", "creator"),
            ("submitted_by", "submitter"),
            ("approved_by", "approver"),
            ("rejected_by", "rejector"),
            ("cancelled_by", "canceller"),
        ):
            user = fact.get(key) or {}
            if user.get("user_id") == user_id:
                params = _user_merge_params(prefix, user)
                return {
                    "given_name": params[f"{prefix}_given_name"],
                    "family_name": params[f"{prefix}_family_name"],
                    "title": params[f"{prefix}_title"],
                    "lob": params[f"{prefix}_lob"],
                    "roles": params[f"{prefix}_roles"],
                    "supervisor_id": params[f"{prefix}_supervisor_id"],
                }
        return {}

    async def _write_payment_lifecycle_edge(
        self,
        tx: Any,
        *,
        edge_type: str,
        user_id: str,
        version_key: str,
        at: str | None,
        user_params: dict[str, Any] | None = None,
    ) -> None:
        user_params = user_params or {}
        await tx.run(
            f"""
            MERGE (u:User {{user_id: $user_id}})
            SET   u.given_name    = coalesce($given_name, u.given_name),
                  u.family_name   = coalesce($family_name, u.family_name),
                  u.display_name  = coalesce(
                      CASE WHEN $family_name IS NOT NULL AND $given_name IS NOT NULL
                           THEN $family_name + ', ' + $given_name + ' (' + $user_id + ')'
                           ELSE null END,
                      u.display_name),
                  u.title         = coalesce($title, u.title),
                  u.lob           = coalesce($lob, u.lob),
                  u.roles         = coalesce($roles, u.roles),
                  u.supervisor_id = coalesce($supervisor_id, u.supervisor_id)
            WITH u
            MATCH (v:PaymentVersion {{version_key: $version_key}})
            MERGE (u)-[r:{edge_type}]->(v)
            SET r.at = $at
            """,
            user_id=user_id,
            version_key=version_key,
            at=at,
            given_name=user_params.get("given_name"),
            family_name=user_params.get("family_name"),
            title=user_params.get("title"),
            lob=user_params.get("lob"),
            roles=user_params.get("roles"),
            supervisor_id=user_params.get("supervisor_id"),
        )

    async def upsert_instruction_fact(
        self,
        fact: dict[str, Any],
        *,
        multimodal: MultimodalWrite | None = None,
    ) -> None:
        """Upsert instruction state from an InstructionFact event (instructions topic).

        Maintains:
          • Instruction node (with is_expired flag from dates)
          • InstructionVersion node (with status, financial details, expiry)
          • CURRENT relationship on the latest version
          • Creator, approver, rejector User nodes + CREATED/APPROVED/REJECTED rels
          • LOB / ProfitCenter node + OWNED_BY, BELONGS_TO rels
          • CONFLICTS_WITH cross-instruction rels
        """
        if self._driver is None:
            raise RuntimeError("Neo4j writer not connected")

        snap = fact.get("instruction_snapshot") or {}
        instruction_id = fact.get("instruction_id") or snap.get("instruction_id")
        if not instruction_id:
            return

        version_number = fact.get("version_number", 0)
        version_key = _instruction_version_key(instruction_id, version_number)
        action = fact.get("action", "")
        timestamp = fact.get("timestamp")

        owning_lob = snap.get("owning_lob") or ""
        status = snap.get("status") or ""
        instruction_type = snap.get("instruction_type") or ""
        wire_scope = snap.get("wire_scope") or ""
        currency = snap.get("currency") or ""
        effective_date = snap.get("effective_date") or ""
        end_date = snap.get("end_date") or ""

        creditor = snap.get("creditor") or {}
        creditor_account = snap.get("creditor_account") or {}
        creditor_agent_fi = (snap.get("creditor_agent") or {}).get("financial_institution") or {}
        debtor = snap.get("debtor") or {}
        debtor_account = snap.get("debtor_account") or {}
        debtor_agent_fi = (snap.get("debtor_agent") or {}).get("financial_institution") or {}

        created_by = snap.get("created_by") or {}
        approved_by = snap.get("approved_by") or {}
        rejected_by = snap.get("rejected_by") or {}

        creator_user_id = created_by.get("user_id")
        approver_user_id = approved_by.get("user_id")
        rejector_user_id = rejected_by.get("user_id")

        actor_user_id = fact.get("actor_user_id")
        auth_params = authorization_fact_neo4j_params(fact)

        valid_out = fact.get("valid_out")
        used_by = snap.get("used_by")
        is_current = is_version_open(valid_out)
        created_at = timestamp or fact.get("valid_in") or snap.get("created_at")
        prev_version_key = (
            _instruction_version_key(instruction_id, version_number - 1)
            if version_number > 1
            else None
        )

        lifecycle_edge = INSTRUCTION_ACTION_TO_EDGE.get(action)
        lifecycle_user_id, lifecycle_extra = instruction_lifecycle_actor(fact)

        query = """
        // ── Instruction root node ────────────────────────────────────────────────
        MERGE (i:Instruction {instruction_id: $instruction_id})
        SET   i.owning_lob       = $owning_lob,
              i.instruction_type = $instruction_type,
              i.wire_scope       = $wire_scope,
              i.currency         = $currency

        // ── InstructionVersion node ──────────────────────────────────────────────
        MERGE (v:InstructionVersion {version_key: $version_key})
        SET   v.instruction_id     = $instruction_id,
              v.version_number     = $version_number,
              v.status             = $status,
              v.action             = $action,
              v.timestamp          = $timestamp,
              v.created_at         = $created_at,
              v.used_by            = $used_by,
              v.owning_lob         = $owning_lob,
              v.instruction_type   = $instruction_type,
              v.wire_scope         = $wire_scope,
              v.currency           = $currency,
              v.effective_date     = $effective_date,
              v.end_date           = $end_date,
              v.creditor_name      = $creditor_name,
              v.creditor_account   = $creditor_account,
              v.creditor_scheme    = $creditor_scheme,
              v.creditor_bic       = $creditor_bic,
              v.debtor_name        = $debtor_name,
              v.debtor_account     = $debtor_account,
              v.debtor_bic         = $debtor_bic,
              v.creator_user_id    = $creator_user_id,
              v.approver_user_id   = $approver_user_id,
              v.rejector_user_id   = $rejector_user_id,
              v.approved_at        = coalesce($approved_at, v.approved_at),
              v.submitted_at       = coalesce($submitted_at, v.submitted_at),
              v.rejected_at        = coalesce($rejected_at, v.rejected_at),
              v.cancelled_at       = coalesce($cancelled_at, v.cancelled_at),
              v.authorization_summary = coalesce($authorization_summary, v.authorization_summary),
              v.authorization_basis   = coalesce($authorization_basis, v.authorization_basis),
              v.is_expired         = (
                  $end_date IS NOT NULL AND $end_date <> '' AND
                  date(substring($end_date, 0, 10)) < date()
              )
        MERGE (i)-[:HAS_VERSION]->(v)

        // ── SUPERSEDES chain ─────────────────────────────────────────────────────
        WITH i, v
        FOREACH (_ IN CASE WHEN $prev_version_key IS NOT NULL THEN [1] ELSE [] END |
            MERGE (prev:InstructionVersion {version_key: $prev_version_key})
            MERGE (v)-[:SUPERSEDES]->(prev)
        )

        // ── Mark CURRENT version (open out only; never regress) ──────────────────
        WITH i, v
        OPTIONAL MATCH (i)-[:CURRENT]->(existing:InstructionVersion)
        WITH i, v, existing
        WHERE $is_current
          AND (
                existing IS NULL
             OR (
                    $status IS NOT NULL AND $status <> ''
                    AND (
                        v.version_number >= existing.version_number
                        OR existing.status IS NULL OR existing.status = ''
                    )
                )
          )
        OPTIONAL MATCH (i)-[old:CURRENT]->(:InstructionVersion)
        DELETE old
        MERGE  (i)-[:CURRENT]->(v)
        SET    i.current_status = $status,
               i.current_version_number = $version_number,
               i.current_used_by = CASE WHEN $status = 'USED' THEN $used_by ELSE null END

        // ── LOB / ProfitCenter ──────────────────────────────────────────────────
        WITH i, v
        MERGE (lob:ProfitCenter {name: $owning_lob})
        MERGE (i)-[:OWNED_BY]->(lob)
        MERGE (v)-[:BELONGS_TO]->(lob)
        """

        params: dict[str, Any] = {
            "instruction_id": instruction_id,
            "version_key": version_key,
            "version_number": version_number,
            "action": action,
            "timestamp": timestamp,
            "created_at": created_at,
            "used_by": used_by,
            "is_current": is_current,
            "prev_version_key": prev_version_key,
            "owning_lob": owning_lob,
            "status": status,
            "instruction_type": instruction_type,
            "wire_scope": wire_scope,
            "currency": currency,
            "effective_date": effective_date,
            "end_date": end_date,
            "creditor_name": creditor.get("name"),
            "creditor_account": creditor_account.get("identification"),
            "creditor_scheme": creditor_account.get("identification_scheme"),
            "creditor_bic": creditor_agent_fi.get("identification"),
            "debtor_name": debtor.get("name"),
            "debtor_account": debtor_account.get("identification"),
            "debtor_bic": debtor_agent_fi.get("identification"),
            "creator_user_id": creator_user_id,
            "creator_given_name": created_by.get("given_name"),
            "creator_family_name": created_by.get("family_name"),
            "creator_title": created_by.get("title"),
            "creator_lob": created_by.get("lob"),
            "creator_roles": _roles_json(created_by.get("roles")),
            "creator_supervisor_id": created_by.get("supervisor_id"),
            "approver_user_id": approver_user_id,
            "approver_given_name": approved_by.get("given_name"),
            "approver_family_name": approved_by.get("family_name"),
            "approver_title": approved_by.get("title"),
            "approver_lob": approved_by.get("lob"),
            "approver_roles": _roles_json(approved_by.get("roles")),
            "approver_supervisor_id": approved_by.get("supervisor_id"),
            "rejector_user_id": rejector_user_id,
            "rejector_given_name": rejected_by.get("given_name"),
            "rejector_family_name": rejected_by.get("family_name"),
            "rejector_title": rejected_by.get("title"),
            "rejector_lob": rejected_by.get("lob"),
            "rejector_roles": _roles_json(rejected_by.get("roles")),
            "rejector_supervisor_id": rejected_by.get("supervisor_id"),
            "actor_user_id": actor_user_id,
            "actor_given_name": fact.get("actor_given_name"),
            "actor_family_name": fact.get("actor_family_name"),
            "actor_title": fact.get("actor_title"),
            "actor_lob": fact.get("actor_lob"),
            "actor_roles": _roles_json(fact.get("actor_roles")),
            "actor_supervisor_id": fact.get("actor_supervisor_id"),
            **auth_params,
        }

        conflict_query = """
            MATCH (v1:InstructionVersion {
                creditor_account: $creditor_account,
                currency:         $currency
            })
            WHERE v1.instruction_id <> $instruction_id
            MATCH (i1:Instruction {instruction_id: $instruction_id})-[:CURRENT]->(cv1:InstructionVersion)
            MATCH (i2:Instruction)-[:CURRENT]->(v1)
            WHERE i2.instruction_id <> $instruction_id
              AND cv1.status IN ['APPROVED', 'SUBMITTED']
              AND v1.status  IN ['APPROVED', 'SUBMITTED']
            MERGE (i1)-[:CONFLICTS_WITH]->(i2)
            MERGE (i2)-[:CONFLICTS_WITH]->(i1)
            """

        async with self._driver.session() as session:
            tx = await session.begin_transaction()
            try:
                await tx.run(query, **params)
                if creditor_account.get("identification") and currency:
                    await tx.run(
                        conflict_query,
                        creditor_account=creditor_account["identification"],
                        currency=currency,
                        instruction_id=instruction_id,
                    )
                if lifecycle_edge and lifecycle_user_id:
                    await self._write_lifecycle_edge(
                        tx,
                        edge_type=lifecycle_edge,
                        user_id=lifecycle_user_id,
                        version_key=version_key,
                        at=timestamp,
                        extra_props=lifecycle_extra,
                        user_params=self._instruction_lifecycle_user_params(fact, lifecycle_user_id),
                    )
                if action == "RELEASE_USE":
                    payment_id = release_use_payment_id(fact)
                    if payment_id:
                        await tx.run(
                            """
                            MATCH (i:Instruction {instruction_id: $instruction_id})
                            MATCH (p:Payment {payment_id: $payment_id})
                            OPTIONAL MATCH (p)-[c:CONSUMED]->(i)
                            DELETE c
                            WITH i, p
                            OPTIONAL MATCH (i)-[cb:CONSUMED_BY]->(p)
                            DELETE cb
                            """,
                            instruction_id=instruction_id,
                            payment_id=payment_id,
                        )
                await upsert_multimodal_writes_in_tx(tx, multimodal)
                await tx.commit()
            except Exception:
                await tx.rollback()
                raise

        logger.debug(
            "upserted instruction fact instruction_id=%s action=%s version=%s",
            instruction_id,
            action,
            version_number,
        )

    async def upsert_payment_security_event(
        self,
        event: dict[str, Any],
        *,
        multimodal: MultimodalWrite | None = None,
    ) -> None:
        """Write a PaymentSecurityEvent into Neo4j.

        Creates/merges:
          - SecurityEvent node (with payment_id property)
          - Payment root + PaymentVersion (append-only version chain)
          - User actor node + ACTED_AS relationship
          - (SecurityEvent)-[:TARGETS_PAYMENT]->(Payment)
          - (SecurityEvent)-[:TARGETS_PAYMENT_VERSION]->(PaymentVersion)
          - (SecurityEvent)-[:INVOLVES_LOB]->(ProfitCenter)
        """
        if self._driver is None:
            raise RuntimeError("Neo4j writer not connected")

        actor = event.get("actor") or {}
        resource = event.get("resource") or {}
        event_ctx = event.get("event") or {}
        source = event.get("source") or {}

        event_id = event.get("event_id", "")
        payment_id = resource.get("id", "")
        instruction_id = resource.get("instruction_id", "")
        owning_lob = resource.get("owning_lob", "")
        payment_version = _payment_version_number(event)
        payment_version_key = _payment_version_key(payment_id, payment_version)
        auth_params = authorization_neo4j_params(event)

        async with self._driver.session() as session:
            tx = await session.begin_transaction()
            try:
                # SecurityEvent node
                await tx.run(
                    """
                    MERGE (e:SecurityEvent {event_id: $event_id})
                    SET e.timestamp        = $timestamp,
                        e.severity         = $severity,
                        e.message          = $message,
                        e.action           = $action,
                        e.outcome          = $outcome,
                        e.reason           = $reason,
                        e.payment_id       = $payment_id,
                        e.source_application = $source_application,
                        e.source_version   = $source_version,
                        e.owning_lob       = $owning_lob,
                        e.authorization_summary = $authorization_summary,
                        e.authorization_decision = $authorization_decision,
                        e.authorization_basis = $authorization_basis,
                        e.authorization_violations = $authorization_violations
                    """,
                    event_id=event_id,
                    timestamp=event.get("timestamp"),
                    severity=event.get("severity"),
                    message=event.get("message"),
                    action=event_ctx.get("action"),
                    outcome=event_ctx.get("outcome"),
                    reason=event_ctx.get("reason"),
                    payment_id=payment_id,
                    source_application=source.get("application"),
                    source_version=source.get("version"),
                    owning_lob=owning_lob,
                    **auth_params,
                )

                # Actor + ACTED_AS
                if actor.get("user_id"):
                    await tx.run(
                        """
                        MERGE (u:User {user_id: $user_id})
                        SET u.given_name    = coalesce($given_name, u.given_name),
                            u.family_name   = coalesce($family_name, u.family_name),
                            u.display_name  = coalesce(
                                CASE WHEN $family_name IS NOT NULL AND $given_name IS NOT NULL
                                     THEN $family_name + ', ' + $given_name + ' (' + $user_id + ')'
                                     ELSE null END,
                                u.display_name),
                            u.title         = coalesce($title, u.title),
                            u.lob           = coalesce($lob, u.lob),
                            u.roles         = coalesce($roles, u.roles),
                            u.supervisor_id = coalesce($supervisor_id, u.supervisor_id)
                        WITH u
                        MATCH (e:SecurityEvent {event_id: $event_id})
                        MERGE (u)-[:ACTED_AS]->(e)
                        """,
                        user_id=actor["user_id"],
                        given_name=actor.get("given_name"),
                        family_name=actor.get("family_name"),
                        title=actor.get("title"),
                        lob=actor.get("lob"),
                        roles=_roles_json(actor.get("roles")),
                        supervisor_id=actor.get("supervisor_id"),
                        event_id=event_id,
                    )
                    if actor.get("supervisor_id"):
                        await tx.run(
                            """
                            MERGE (u:User {user_id: $user_id})
                            MERGE (s:User {user_id: $supervisor_id})
                            MERGE (u)-[:REPORTS_TO]->(s)
                            """,
                            user_id=actor["user_id"],
                            supervisor_id=actor["supervisor_id"],
                        )

                # Payment root + sparse version + FOR (audit only)
                if payment_id:
                    await tx.run(
                        """
                        MERGE (pay:Payment {payment_id: $payment_id})
                        SET pay.instruction_id = coalesce($instruction_id, pay.instruction_id)
                        MERGE (v:PaymentVersion {version_key: $version_key})
                        SET v.payment_id     = $payment_id,
                            v.version_number = $version_number,
                            v.owning_lob     = coalesce($owning_lob, v.owning_lob)
                        MERGE (pay)-[:HAS_VERSION]->(v)
                        WITH pay, v
                        MATCH (e:SecurityEvent {event_id: $event_id})
                        MERGE (e)-[:FOR]->(v)
                        """,
                        payment_id=payment_id,
                        instruction_id=instruction_id,
                        version_key=payment_version_key,
                        version_number=payment_version,
                        owning_lob=owning_lob,
                        event_id=event_id,
                    )

                # INVOLVES_LOB
                if owning_lob:
                    await tx.run(
                        """
                        MATCH (e:SecurityEvent {event_id: $event_id})
                        MERGE (pc:ProfitCenter {lob: $owning_lob})
                        MERGE (e)-[:INVOLVES_LOB]->(pc)
                        """,
                        event_id=event_id,
                        owning_lob=owning_lob,
                    )

                await upsert_multimodal_writes_in_tx(tx, multimodal)
                await tx.commit()
            except Exception:
                await tx.rollback()
                raise

    async def upsert_payment_fact(
        self,
        fact: dict[str, Any],
        *,
        multimodal: MultimodalWrite | None = None,
    ) -> None:
        """Write a Payment fact (from payments topic) into Neo4j.

        Maintains:
          • Payment node (stable business key)
          • PaymentVersion node (append-only lifecycle snapshot)
          • CURRENT relationship on the latest version
          • Creator, submitter, approver, rejector User nodes + payment rels
          • (Instruction)-[:HAS_PAYMENT]->(Payment)
        """
        if self._driver is None:
            raise RuntimeError("Neo4j writer not connected")

        payment_id = fact.get("payment_id", "")
        if not payment_id:
            return

        instruction_id = fact.get("instruction_id", "")
        created_by = fact.get("created_by") or {}
        submitted_by = fact.get("submitted_by") or {}
        approved_by = fact.get("approved_by") or {}
        rejected_by = fact.get("rejected_by") or {}
        payment_version = _payment_version_number(fact)
        payment_version_key = _payment_version_key(payment_id, payment_version)
        timestamp = fact.get("timestamp") or fact.get("updated_at")
        valid_out = fact.get("valid_out")
        is_current = is_version_open(valid_out)
        action = fact.get("action", "")
        instruction_type = fact.get("instruction_type") or ""
        prev_version_key = (
            _payment_version_key(payment_id, payment_version - 1)
            if payment_version > 1
            else None
        )
        lifecycle_edge = PAYMENT_ACTION_TO_EDGE.get(action)
        lifecycle_user_id = payment_lifecycle_actor(fact)

        query = """
        // ── Payment root node ────────────────────────────────────────────────────
        MERGE (pay:Payment {payment_id: $payment_id})
        SET   pay.instruction_id = $instruction_id

        // ── PaymentVersion node ──────────────────────────────────────────────────
        MERGE (v:PaymentVersion {version_key: $version_key})
        SET   v.payment_id         = $payment_id,
              v.version_number     = $version_number,
              v.status             = $status,
              v.action             = $action,
              v.timestamp          = $timestamp,
              v.instruction_id     = $instruction_id,
              v.amount             = $amount,
              v.currency           = $currency,
              v.value_date         = $value_date,
              v.owning_lob         = $owning_lob,
              v.instruction_type   = $instruction_type,
              v.instruction_version = $instruction_version,
              v.cancellation_reason = coalesce($cancellation_reason, v.cancellation_reason),
              v.cancelled_by_system = coalesce($cancelled_by_system, v.cancelled_by_system),
              v.creator_user_id    = $creator_user_id,
              v.submitter_user_id  = $submitter_user_id,
              v.approver_user_id   = $approver_user_id,
              v.rejector_user_id   = $rejector_user_id,
              v.created_at         = $created_at,
              v.updated_at         = $updated_at,
              v.submitted_at       = coalesce($submitted_at, v.submitted_at),
              v.approved_at        = coalesce($approved_at, v.approved_at),
              v.rejected_at        = coalesce($rejected_at, v.rejected_at),
              v.cancelled_at       = coalesce($cancelled_at, v.cancelled_at)
        MERGE (pay)-[:HAS_VERSION]->(v)

        // ── SUPERSEDES chain ─────────────────────────────────────────────────────
        WITH pay, v
        FOREACH (_ IN CASE WHEN $prev_version_key IS NOT NULL THEN [1] ELSE [] END |
            MERGE (prev:PaymentVersion {version_key: $prev_version_key})
            MERGE (v)-[:SUPERSEDES]->(prev)
        )

        // ── Mark CURRENT version (open out only; never regress) ───────────────────
        WITH pay, v
        OPTIONAL MATCH (pay)-[:CURRENT]->(existing:PaymentVersion)
        WITH pay, v, existing
        WHERE $is_current
          AND (
                existing IS NULL
             OR (
                    $status IS NOT NULL
                    AND (
                        v.version_number >= existing.version_number
                        OR existing.status IS NULL
                    )
                )
          )
        OPTIONAL MATCH (pay)-[old:CURRENT]->(:PaymentVersion)
        DELETE old
        MERGE  (pay)-[:CURRENT]->(v)
        SET    pay.current_status = $status,
               pay.current_version_number = $version_number,
               pay.current_amount = $amount,
               pay.current_currency = $currency

        // ── Instruction structural links ─────────────────────────────────────────
        WITH pay, v
        FOREACH (_ IN CASE WHEN $instruction_id IS NOT NULL AND $instruction_id <> '' THEN [1] ELSE [] END |
            MERGE (i:Instruction {instruction_id: $instruction_id})
            MERGE (i)-[:HAS_PAYMENT]->(pay)
            MERGE (pay)-[:FOR_INSTRUCTION]->(i)
        )

        // ── SINGLE_USE consumption on submit ────────────────────────────────────
        WITH pay, v
        FOREACH (_ IN CASE
            WHEN $action IN ['SUBMIT', 'SUBMIT_PAYMENT']
             AND $instruction_type = 'SINGLE_USE'
             AND $instruction_id IS NOT NULL AND $instruction_id <> ''
            THEN [1] ELSE [] END |
            MERGE (i:Instruction {instruction_id: $instruction_id})
            MERGE (pay)-[:CONSUMED]->(i)
            MERGE (i)-[:CONSUMED_BY]->(pay)
        )
        """

        creator_user_id = created_by.get("user_id")
        submitter_user_id = submitted_by.get("user_id")
        approver_user_id = approved_by.get("user_id")
        rejector_user_id = rejected_by.get("user_id")

        params: dict[str, Any] = {
            "payment_id": payment_id,
            "instruction_id": instruction_id,
            "version_key": payment_version_key,
            "version_number": payment_version,
            "action": action,
            "status": fact.get("status"),
            "timestamp": timestamp,
            "is_current": is_current,
            "prev_version_key": prev_version_key,
            "amount": fact.get("amount"),
            "currency": fact.get("currency"),
            "value_date": fact.get("value_date"),
            "owning_lob": fact.get("owning_lob"),
            "instruction_type": instruction_type,
            "instruction_version": fact.get("instruction_version"),
            "cancellation_reason": fact.get("cancellation_reason"),
            "cancelled_by_system": fact.get("cancelled_by_system"),
            "creator_user_id": creator_user_id,
            "submitter_user_id": submitter_user_id,
            "approver_user_id": approver_user_id,
            "rejector_user_id": rejector_user_id,
            "created_at": fact.get("created_at") or timestamp,
            "updated_at": fact.get("updated_at"),
            "submitted_at": fact.get("submitted_at"),
            "approved_at": fact.get("approved_at"),
            "rejected_at": fact.get("rejected_at"),
            "cancelled_at": fact.get("cancelled_at"),
            "creator_given_name": created_by.get("given_name"),
            "creator_family_name": created_by.get("family_name"),
            "creator_title": created_by.get("title"),
            "creator_lob": created_by.get("lob"),
            "creator_supervisor_id": created_by.get("supervisor_id"),
            "submitter_given_name": submitted_by.get("given_name"),
            "submitter_family_name": submitted_by.get("family_name"),
            "submitter_title": submitted_by.get("title"),
            "submitter_lob": submitted_by.get("lob"),
            "submitter_supervisor_id": submitted_by.get("supervisor_id"),
            "approver_given_name": approved_by.get("given_name"),
            "approver_family_name": approved_by.get("family_name"),
            "approver_title": approved_by.get("title"),
            "approver_lob": approved_by.get("lob"),
            "approver_supervisor_id": approved_by.get("supervisor_id"),
            "rejector_given_name": rejected_by.get("given_name"),
            "rejector_family_name": rejected_by.get("family_name"),
            "rejector_title": rejected_by.get("title"),
            "rejector_lob": rejected_by.get("lob"),
            "rejector_supervisor_id": rejected_by.get("supervisor_id"),
        }

        async with self._driver.session() as session:
            tx = await session.begin_transaction()
            try:
                await tx.run(query, **params)

                if lifecycle_edge and lifecycle_user_id:
                    await self._write_payment_lifecycle_edge(
                        tx,
                        edge_type=lifecycle_edge,
                        user_id=lifecycle_user_id,
                        version_key=payment_version_key,
                        at=timestamp,
                        user_params=self._payment_lifecycle_user_params(fact, lifecycle_user_id),
                    )

                for user in (created_by, submitted_by, approved_by, rejected_by):
                    if user.get("user_id") and user.get("supervisor_id"):
                        await tx.run(
                            """
                            MERGE (u:User {user_id: $user_id})
                            MERGE (s:User {user_id: $supervisor_id})
                            MERGE (u)-[:REPORTS_TO]->(s)
                            """,
                            user_id=user["user_id"],
                            supervisor_id=user["supervisor_id"],
                        )

                await upsert_multimodal_writes_in_tx(tx, multimodal)
                await tx.commit()
            except Exception:
                await tx.rollback()
                raise

        logger.debug(
            "upserted payment fact payment_id=%s status=%s version=%s",
            payment_id,
            fact.get("status"),
            payment_version,
        )

    async def run_read_cypher(self, cypher: str) -> list[dict[str, Any]]:
        """Execute a validated read-only Cypher query and return rows as plain dicts.

        The caller is responsible for pre-validating the query with
        ``validate_read_only_cypher`` before passing it here.  This method opens
        a read-access session so the database layer also enforces read-only mode.
        """
        if self._driver is None:
            raise RuntimeError("Neo4j writer not connected")

        rows: list[dict[str, Any]] = []
        async with self._driver.session(default_access_mode="READ") as session:
            result = await session.run(cypher)
            async for record in result:
                row: dict[str, Any] = {}
                for key in record.keys():
                    value = record[key]
                    if hasattr(value, "items"):
                        row[key] = dict(value.items())
                    elif isinstance(value, list):
                        row[key] = [
                            dict(item.items()) if hasattr(item, "items") else item
                            for item in value
                        ]
                    else:
                        row[key] = value
                rows.append(row)
        return rows
