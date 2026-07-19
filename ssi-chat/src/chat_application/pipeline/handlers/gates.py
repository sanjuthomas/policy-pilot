from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from chat_application.auth.capabilities import ChatCapabilities
from chat_application.models import SearchMode

TOOL_PATHS = frozenset(
    {
        "policy_summary",
        "policy_directory",
        "person_permissions",
        "eligibility",
    }
)
SKILL_PATHS = frozenset({"skill"})
ME_PATHS = frozenset({"me"})
NEO4J_DIRECT_PATHS = frozenset({"neo4j_direct"})

# Mutations stay on Payments (+ all). Investigation modes never run skills.
SKILL_MODES = frozenset({"payments", "all"})
# Live OPA / directory / person tools stay on Policies mode.
TOOL_MODES = frozenset({"policies"})
# Neo4j + vector investigation (and path-owned neo4j_direct).
INVESTIGATE_MODES = frozenset({"events", "instructions", "payments", "all"})


class HandlerLane(str, Enum):
    SKILL = "skill"
    ME = "me"
    TOOLS = "tools"
    NEO4J_DIRECT = "neo4j_direct"
    INVESTIGATE = "investigate"


class DenialReason(str, Enum):
    SKILL_WRONG_MODE = "skill_wrong_mode"
    SKILL_NOT_CREATOR = "skill_not_creator"
    TOOLS_WRONG_MODE = "tools_wrong_mode"
    TOOLS_NOT_COMPLIANCE = "tools_not_compliance"
    POLICIES_MODE_OPERATIONAL = "policies_mode_operational"


@dataclass(frozen=True)
class LaneAccess:
    """Result of capability × mode fence for a routed path."""

    allowed: bool
    lane: HandlerLane
    denial: DenialReason | None = None


def lane_for_path(path: str | None) -> HandlerLane:
    if path in SKILL_PATHS:
        return HandlerLane.SKILL
    if path in ME_PATHS:
        return HandlerLane.ME
    if path in TOOL_PATHS:
        return HandlerLane.TOOLS
    if path in NEO4J_DIRECT_PATHS:
        return HandlerLane.NEO4J_DIRECT
    return HandlerLane.INVESTIGATE


def resolve_lane_access(
    *,
    path: str | None,
    mode: SearchMode,
    capabilities: ChatCapabilities,
) -> LaneAccess:
    """Hard fence: skills / tools / neo4j_direct / investigate are separate surfaces."""
    lane = lane_for_path(path)

    if lane == HandlerLane.SKILL:
        if mode not in SKILL_MODES:
            return LaneAccess(False, lane, DenialReason.SKILL_WRONG_MODE)
        if not (
            capabilities.can_create_payment
            or capabilities.can_approve_payment
            or capabilities.can_cancel_payment
        ):
            return LaneAccess(False, lane, DenialReason.SKILL_NOT_CREATOR)
        return LaneAccess(True, lane)

    if lane == HandlerLane.TOOLS:
        if mode not in TOOL_MODES:
            return LaneAccess(False, lane, DenialReason.TOOLS_WRONG_MODE)
        if not capabilities.can_use_policies:
            return LaneAccess(False, lane, DenialReason.TOOLS_NOT_COMPLIANCE)
        return LaneAccess(True, lane)

    if lane == HandlerLane.ME:
        return LaneAccess(True, lane)

    # neo4j_direct + investigate share investigation modes
    if mode == "policies":
        if capabilities.can_use_policies:
            # Dedicated tool paths already handled above; policies fallthrough → tools guidance.
            return LaneAccess(True, HandlerLane.TOOLS)
        return LaneAccess(False, HandlerLane.TOOLS, DenialReason.POLICIES_MODE_OPERATIONAL)

    if mode not in INVESTIGATE_MODES:
        return LaneAccess(False, lane, DenialReason.TOOLS_WRONG_MODE)

    return LaneAccess(True, lane)


def denial_message(reason: DenialReason) -> tuple[str, Literal["skill", "eligibility", "formatter"]]:
    """User-facing denial copy and observability path/synthesis hints."""
    if reason == DenialReason.SKILL_WRONG_MODE:
        return (
            "Payment mutation skills are available in **Payments** mode. "
            "Switch modes and ask again (create / submit / approve with the required ids).",
            "skill",
        )
    if reason == DenialReason.SKILL_NOT_CREATOR:
        return (
            "Payment mutation skills require **PAYMENT_CREATOR** (create/submit) or "
            "**FUNDING_APPROVER** (approve). "
            "Sign in as an operational payment user or switch to Events / Instructions to investigate.",
            "skill",
        )
    if reason == DenialReason.TOOLS_WRONG_MODE:
        return (
            "Live policy tools (summaries, directory, eligibility) are available in **Policies** mode. "
            "Switch to Policies and ask again, or use Events / Instructions / Payments for graph investigation.",
            "eligibility",
        )
    if reason in (DenialReason.TOOLS_NOT_COMPLIANCE, DenialReason.POLICIES_MODE_OPERATIONAL):
        return (
            "Policies mode requires a signed-in PolicyPilot session. "
            "Sign in and ask again, or switch to Payments / Events / Instructions mode.",
            "eligibility",
        )
    return ("This action is not available for your role or mode.", "formatter")
