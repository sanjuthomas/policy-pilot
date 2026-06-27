from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ilm.kafka_publisher import kafka_publisher
from ilm.models.enums import LifecycleAction
from ilm.models.instruction_fact import InstructionFact
from ilm.models.api import Subject
from ilm.models.instruction import CashSettlementInstruction
from ilm.opa import OpaClient
from ilm.security_event_repair import _subject_from_actor, repair_security_event_authorization
from ilm.security_event_repository import SecurityEventRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


class RepairAuthorizationResponse(BaseModel):
    scanned: int
    repaired: int
    skipped: int
    republished_facts: int
    logs: list[str] = Field(default_factory=list)


@router.post("/repair-authorization", response_model=RepairAuthorizationResponse)
async def repair_authorization(limit: int = 500) -> RepairAuthorizationResponse:
    """Backfill missing OPA authorization on historical success security events."""
    repo = SecurityEventRepository()
    opa = OpaClient()
    documents = await repo.find_missing_authorization(limit=limit)

    repaired = 0
    skipped = 0
    republished_facts = 0
    logs: list[str] = []

    for document in documents:
        event_id = document.get("event_id", "?")
        action = (document.get("event") or {}).get("action", "?")
        try:
            fixed = await repair_security_event_authorization(document, opa=opa)
        except Exception as exc:
            skipped += 1
            logs.append(f"{event_id} ({action}) error: {exc}")
            logger.exception("authorization repair failed event_id=%s", event_id)
            continue

        if fixed is None:
            skipped += 1
            continue

        await repo.replace_document(fixed)
        repaired += 1
        summary = (fixed.get("details") or {}).get("authorization", {}).get("summary", "")
        logs.append(f"{event_id} ({action}) repaired: {summary[:120]}…")

        event_action = (fixed.get("event") or {}).get("action")
        if event_action == LifecycleAction.APPROVE.value:
            snapshot = fixed.get("instruction_snapshot") or {}
            actor = fixed.get("actor") or {}
            resource = fixed.get("resource") or {}
            authorization = (fixed.get("details") or {}).get("authorization")
            if snapshot and actor.get("user_id") and authorization:
                subject = _subject_from_actor(actor)
                instruction = CashSettlementInstruction.model_validate(snapshot)
                fact = InstructionFact.from_instruction(
                    LifecycleAction(event_action),
                    subject,
                    instruction,
                    version_number=int(resource.get("version_number") or 0),
                    authorization=authorization,
                )
                await kafka_publisher.publish_instruction_fact(fact.model_dump(mode="json"))
                republished_facts += 1

    return RepairAuthorizationResponse(
        scanned=len(documents),
        repaired=repaired,
        skipped=skipped,
        republished_facts=republished_facts,
        logs=logs[:50],
    )


@router.post("/republish-approve-events", response_model=RepairAuthorizationResponse)
async def republish_approve_events(limit: int = 500) -> RepairAuthorizationResponse:
    """Re-publish APPROVE security events (and facts) so ETL refreshes instruction-state authorization."""
    repo = SecurityEventRepository()
    cursor = repo.collection.find(
        {
            "event.action": LifecycleAction.APPROVE.value,
            "event.outcome": "success",
        },
        limit=limit,
    )
    documents = [doc async for doc in cursor]

    republished = 0
    republished_facts = 0
    logs: list[str] = []

    for document in documents:
        event_id = document.get("event_id", "?")
        payload = dict(document)
        payload.pop("_id", None)
        await repo.publish(payload)
        republished += 1

        authorization = (payload.get("details") or {}).get("authorization")
        snapshot = payload.get("instruction_snapshot") or {}
        actor = payload.get("actor") or {}
        resource = payload.get("resource") or {}
        if authorization and snapshot and actor.get("user_id"):
            subject = _subject_from_actor(actor)
            instruction = CashSettlementInstruction.model_validate(snapshot)
            fact = InstructionFact.from_instruction(
                LifecycleAction.APPROVE,
                subject,
                instruction,
                version_number=int(resource.get("version_number") or 0),
                authorization=authorization,
            )
            await kafka_publisher.publish_instruction_fact(fact.model_dump(mode="json"))
            republished_facts += 1
            logs.append(f"{event_id} republished APPROVE fact")

    return RepairAuthorizationResponse(
        scanned=len(documents),
        repaired=republished,
        skipped=0,
        republished_facts=republished_facts,
        logs=logs[:50],
    )
