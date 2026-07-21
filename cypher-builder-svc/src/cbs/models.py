from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SearchMode = Literal["events", "instructions", "payments", "policies", "all"]


class PlanOptions(BaseModel):
    lob_scope: str | None = None


class PlanRequest(BaseModel):
    question: str = Field(min_length=1)
    mode: SearchMode = "events"
    options: PlanOptions | None = None


class PlannedQuery(BaseModel):
    label: str
    cypher: str


class PlanResponse(BaseModel):
    matched: bool
    intent_id: str | None = None
    strategy: str | None = None
    planned: list[PlannedQuery] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class ValidateRequest(BaseModel):
    cypher: str = Field(min_length=1)


class ValidateResponse(BaseModel):
    ok: bool
    cypher: str | None = None
    error: str | None = None
