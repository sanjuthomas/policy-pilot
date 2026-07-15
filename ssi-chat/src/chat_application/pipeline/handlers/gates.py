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

# Mutations stay on Payments (+ all). Investigation modes never run skills.
SKILL_MODES = frozenset({"payments", "all"})
# Live OPA / directory / person tools stay on Policies mode.
TOOL_MODES = frozenset({"policies"})
# Neo4j + vector investigation.
INVESTIGATE_MODES = frozenset({"events", "instructions", "payments", "all"})


class HandlerLane(str, Enum):
    SKILL = "skill"
    ME = "me"
    TOOLS = "tools"
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
    return HandlerLane.INVESTIGATE


def resolve_lane_access(
    *,
    path: str | None,
    mode: SearchMode,
    capabilities: ChatCapabilities,
) -> LaneAccess:
    """Hard fence: skills / tools / investigate are separate surfaces."""
    lane = lane_for_path(path)

    if lane == HandlerLane.SKILL:
        if mode not in SKILL_MODES:
            return LaneAccess(False, lane, DenialReason.SKILL_WRONG_MODE)
        if not capabilities.can_create_payment:
            return LaneAccess(False, lane, DenialReason.SKILL_NOT_CREATOR)
        return LaneAccess(True, lane)

    if lane == HandlerLane.TOOLS:
        if mode not in TOOL_MODES:
            return LaneAccess(False, lane, DenialReason.TOOLS_WRONG_MODE)
        if not capabilities.is_compliance:
            return LaneAccess(False, lane, DenialReason.TOOLS_NOT_COMPLIANCE)
        return LaneAccess(True, lane)

    if lane == HandlerLane.ME:
        # Me-intents are available in any mode once the subject is authenticated;
        # policies mode still allows me-centric questions for operational users.
        return LaneAccess(True, lane)

    # Investigate (or policies-mode fallthrough after tools)
    if mode == "policies":
        if capabilities.is_compliance:
            # Compliance tools lane should have handled dedicated paths;
            # guidance / empty policies fallthrough is allowed.
            return LaneAccess(True, HandlerLane.TOOLS)
        return LaneAccess(False, HandlerLane.TOOLS, DenialReason.POLICIES_MODE_OPERATIONAL)

    if mode not in INVESTIGATE_MODES:
        return LaneAccess(False, lane, DenialReason.TOOLS_WRONG_MODE)

    return LaneAccess(True, HandlerLane.INVESTIGATE)


def denial_message(reason: DenialReason) -> tuple[str, Literal["skill", "eligibility", "formatter"]]:
    """User-facing denial copy and observability path/synthesis hints."""
    if reason == DenialReason.SKILL_WRONG_MODE:
        return (
            "Payment creation is available in **Payments** mode. "
            "Switch modes and ask again with an instruction id, amount, and value date.",
            "skill",
        )
    if reason == DenialReason.SKILL_NOT_CREATOR:
        return (
            "Creating a payment requires the **PAYMENT_CREATOR** role. "
            "Sign in as a payment creator (e.g. pay-101) or switch to Events / Instructions to investigate.",
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
            "Policies mode is available to compliance analysts. "
            "As an operational user, ask me-centric questions such as "
            "“Are there any other users like me?” or switch to Payments / Events mode.",
            "eligibility",
        )
    return ("This action is not available for your role or mode.", "formatter")
