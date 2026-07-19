from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from chat_application.models import SearchMode
from chat_application.pipeline.heuristic_strategy import (
    heuristic_router_decision,
    prefer_vector_for_open_narrative,
)
from chat_application.pipeline.models import RouterDecision

if TYPE_CHECKING:
    from chat_application.gemini.client import PolicyPilotMlClient

logger = logging.getLogger(__name__)


async def route_question(
    ml_client: PolicyPilotMlClient,
    message: str,
    *,
    mode: SearchMode,
) -> RouterDecision:
    try:
        decision = await ml_client.route_query(message, mode=mode)
    except Exception as exc:
        logger.warning("LLM router failed, using heuristic fallback: %s", exc)
        decision = heuristic_router_decision(message, mode=mode)
    return prefer_vector_for_open_narrative(decision, message, mode=mode)
