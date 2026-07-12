from typing import Any, Literal

from pydantic import BaseModel, Field

SearchMode = Literal["events", "instructions", "payments", "policies", "all"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=40)
    mode: SearchMode = "events"


class ChatFeedbackRequest(BaseModel):
    rating: Literal["up", "down"]
    mode: SearchMode
    path: str = Field(min_length=1)
    cypher_provenance: str = Field(min_length=1)
    answer_synthesis: str = Field(min_length=1)
    retrieval_strategy: str | None = None
    intent_id: str | None = None
    question_hash: str | None = None


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
    retrieval_strategy: str | None = None


class SkillConfirmationInfo(BaseModel):
    pending_id: str
    skill: str = "create_payment"
    card: dict[str, Any]


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceHit]
    cypher: str | None = None
    graph_rows: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_ms: float | None = None
    generation_ms: float | None = None
    routing: AnswerRoutingInfo | None = None
    skill_activities: list[str] = Field(default_factory=list)
    skill_confirmation: SkillConfirmationInfo | None = None
