from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ExecutionStrategy = Literal["eligibility", "graph", "vector", "hybrid"]
EligibilityTarget = Literal["payment", "instruction"]


class RouterDecision(BaseModel):
    """Semantic routing decision for a chat question."""

    strategy: ExecutionStrategy = Field(
        description=(
            "Retrieval strategy: eligibility (live OPA approver check), "
            "graph (structured Neo4j), vector (semantic policy/docs), "
            "hybrid (both graph and vector)."
        )
    )
    eligibility_target: EligibilityTarget | None = Field(
        default=None,
        description="When strategy is eligibility, whether the target is a payment or instruction.",
    )
    reasoning: str = Field(default="", description="Brief explanation of the routing choice.")
