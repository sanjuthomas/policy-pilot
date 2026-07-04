from typing import Any, Literal

from pydantic import BaseModel, Field

SearchMode = Literal["events", "instructions", "payments", "all"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=40)
    mode: SearchMode = "events"


class SourceHit(BaseModel):
    event_id: str | None = None
    instruction_id: str | None = None
    score: float
    sources: list[str]
    summary: str
    merged: dict[str, Any] | None = None
    security_event: dict[str, Any] | None = None


class AnswerRoutingInfo(BaseModel):
    path: str
    cypher_provenance: str
    answer_synthesis: str
    label: str
    intent_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceHit]
    cypher: str | None = None
    graph_rows: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_ms: float | None = None
    generation_ms: float | None = None
    routing: AnswerRoutingInfo | None = None
