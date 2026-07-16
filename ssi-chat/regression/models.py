from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SearchMode = Literal["events", "instructions", "payments", "all"]

# Primary retrieval path the answer is expected to use (vector still runs in parallel except eligibility).
RetrievalStrategy = Literal[
    "deterministic",
    "graph",
    "vector",
    "eligibility",
    "policy_directory",
    "skill",
]

DEFAULT_PERSONA_PASSWORD = "Password1!"

SKILL_CONFIRM_PATHS: dict[str, str] = {
    "create_payment": "/api/chat/skills/create-payment/confirm",
    "submit_payment": "/api/chat/skills/submit-payment/confirm",
    "approve_payment": "/api/chat/skills/approve-payment/confirm",
}


class SeedStep(BaseModel):
    action: str
    count: int | None = None


class SeedWaitConfig(BaseModel):
    min_security_events: int = 1
    min_multimodal_documents: int = 1
    timeout_seconds: int = 180
    poll_interval_seconds: float = 3.0


class SeedConfig(BaseModel):
    steps: list[SeedStep] = Field(default_factory=list)
    wait: SeedWaitConfig = Field(default_factory=SeedWaitConfig)


class ExpectConfig(BaseModel):
    min_answer_length: int = 1
    answer_contains_any: list[str] = Field(default_factory=list)
    answer_contains_all: list[str] = Field(default_factory=list)
    answer_not_contains: list[str] = Field(default_factory=list)
    answer_has_number: bool = False
    min_sources: int = 0
    min_graph_rows: int = 0
    exact_graph_rows: int | None = None
    requires_cypher: bool = False
    requires_context: list[str] = Field(default_factory=list)
    skip_if_missing_context: bool = True
    # Skill phase-1 (mutation skills)
    intent_id: str | None = None
    require_skill_confirmation: bool = False
    skill_name: str | None = None
    # Retrieval-quality overrides (defaults derived from case ``retrieval`` tag).
    routing_path: str | None = None
    cypher_class: Literal["deterministic", "llm", "none"] | None = None
    answer_synthesis: str | None = None
    source_channels_any: list[str] = Field(default_factory=list)
    max_generation_ms: float | None = None
    require_routing: bool = False
    require_entity_recall: bool = False
    min_groundedness: float | None = None
    min_faithfulness: float | None = None


class ConfirmStep(BaseModel):
    """Optional second step after phase-1 skill confirmation card."""

    decision: Literal["go", "no_go"] = "no_go"
    intent_id: str | None = None
    min_answer_length: int = 1
    answer_contains_any: list[str] = Field(default_factory=list)
    answer_contains_all: list[str] = Field(default_factory=list)
    answer_not_contains: list[str] = Field(default_factory=list)


class RegressionCase(BaseModel):
    id: str
    mode: SearchMode
    retrieval: RetrievalStrategy = Field(
        description=(
            "Primary engine for the answer: deterministic (Neo4j formatter, no LLM synthesis), "
            "graph (Neo4j planned/LLM Cypher authoritative), vector (Neo4j dense primary), "
            "eligibility (live OPA via authorization-service, no vector search), "
            "skill (mutation skill with optional Go / No Go confirm)."
        ),
    )
    question: str
    tags: list[str] = Field(default_factory=list)
    persona: str | None = Field(
        default=None,
        description="ZITADEL user id for chat login (default: compliance analyst).",
    )
    password: str = Field(
        default=DEFAULT_PERSONA_PASSWORD,
        description="Login password for persona (demo users use Password1!).",
    )
    confirm: ConfirmStep | None = None
    expect: ExpectConfig = Field(default_factory=ExpectConfig)


class RegressionSuite(BaseModel):
    version: int = 1
    seed: SeedConfig = Field(default_factory=SeedConfig)
    cases: list[RegressionCase]


class CaseResult(BaseModel):
    id: str
    mode: str
    question: str
    passed: bool
    skipped: bool = False
    reason: str = ""
    answer_preview: str = ""
    sources: int = 0
    graph_rows: int = 0
    retrieval_ms: float | None = None
    generation_ms: float | None = None
    tags: list[str] = Field(default_factory=list)
    retrieval: RetrievalStrategy | None = None
    quality: dict[str, Any] | None = None
    persona: str | None = None


class SuiteResult(BaseModel):
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    cases: list[CaseResult] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    quality_summary: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
