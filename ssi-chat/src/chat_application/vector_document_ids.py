"""Deterministic vector document ids (shared with ssi-indexer ETL)."""

from __future__ import annotations

import uuid


def event_document_id(event_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, event_id))


def instruction_document_id(instruction_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"instruction:{instruction_id}"))


def payment_document_id(payment_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"payment:{payment_id}"))
