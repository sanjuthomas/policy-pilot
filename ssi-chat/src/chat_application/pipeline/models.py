from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

ExecutionStrategy = Literal["eligibility", "graph", "vector", "hybrid"]
EligibilityTarget = Literal["payment", "instruction"]

IntentPath = Literal[
    "skill",
    "me",
    "policy_summary",
    "policy_directory",
    "person_permissions",
    "eligibility",
    "neo4j_direct",
    "graph",
    "vector",
    "hybrid",
]

SkillName = Literal[
    "create_payment",
    "submit_payment",
    "approve_payment",
    "cancel_payment",
]

MeIntentKind = Literal[
    "who_am_i",
    "my_permissions",
    "can_act_on_entity",
    "who_else_can_act",
    "who_can_create",
    "who_covers_lob",
    "waiting_for_me",
    "users_like_me",
]

MeAction = Literal["CREATE", "APPROVE", "UPDATE", "SUBMIT", "REJECT", "CANCEL"]
PolicyDomain = Literal["payment", "instruction"]
PolicyAction = Literal["CREATE", "APPROVE", "UPDATE", "SUBMIT", "REJECT", "CANCEL"]

_RETRIEVAL_PATHS = frozenset({"eligibility", "graph", "vector", "hybrid"})


class RouterDecision(BaseModel):
    """Semantic routing decision for a chat question (Gemini structured output)."""

    path: IntentPath | None = Field(
        default=None,
        description=(
            "Primary intent path. Use skill/me/policy_* for dedicated handlers; "
            "neo4j_direct for known YAML/planned deterministic shapes; "
            "eligibility/graph/vector/hybrid for retrieval."
        ),
    )
    strategy: ExecutionStrategy | None = Field(
        default=None,
        description=(
            "Retrieval strategy when path is eligibility/graph/vector/hybrid. "
            "Ignored for skill/me/policy_*/neo4j_direct paths. Legacy field — prefer path."
        ),
    )
    eligibility_target: EligibilityTarget | None = Field(
        default=None,
        description="When path/strategy is eligibility: payment vs instruction.",
    )
    skill: SkillName | None = Field(
        default=None,
        description="When path is skill: which mutation skill to run.",
    )
    me_kind: MeIntentKind | None = Field(
        default=None,
        description="When path is me: which me-centric intent.",
    )
    me_action: MeAction | None = Field(
        default=None,
        description="When me_kind needs an action (can_act_on_entity, who_can_create, …).",
    )
    me_entity_type: EligibilityTarget | None = Field(
        default=None,
        description="When me intent targets payment vs instruction.",
    )
    policy_domain: PolicyDomain | None = Field(
        default=None,
        description="When path is policy_summary: payment vs instruction domain.",
    )
    policy_action: PolicyAction | None = Field(
        default=None,
        description="When path is policy_summary: OPA action (CREATE, APPROVE, …).",
    )
    person_query: str | None = Field(
        default=None,
        description=(
            "When path is person_permissions: person name or user id "
            "(e.g. 'Kowalski, Anna' or 'pay-203')."
        ),
    )
    reasoning: str = Field(default="", description="Brief explanation of the routing choice.")

    @model_validator(mode="after")
    def _normalize_path_and_strategy(self) -> RouterDecision:
        path = self.path
        strategy = self.strategy

        if path is None and strategy is not None:
            path = strategy
        if path in _RETRIEVAL_PATHS and strategy is None:
            strategy = path  # type: ignore[assignment]
        if path is None:
            path = "hybrid"
            strategy = strategy or "hybrid"

        self.path = path
        self.strategy = strategy

        if path == "skill" and self.skill is None:
            self.skill = "create_payment"
        if path == "policy_summary":
            if self.policy_domain is None:
                self.policy_domain = "payment"
            if self.policy_action is None:
                self.policy_action = "APPROVE"
        return self

    @property
    def retrieval_strategy(self) -> ExecutionStrategy:
        """Strategy used for selective retrieval (never skill/me/policy)."""
        if self.path in _RETRIEVAL_PATHS:
            return self.path  # type: ignore[return-value]
        if self.strategy is not None:
            return self.strategy
        return "hybrid"
