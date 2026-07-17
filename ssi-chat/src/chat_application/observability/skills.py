from __future__ import annotations

from telemetry import get_meter, record_counter

_meter = None


def _get_skill_meter():
    global _meter
    if _meter is None:
        _meter = get_meter("chat.skills", version="0.1.0")
    return _meter


def parse_skill_intent(intent_id: str | None) -> tuple[str, str, str] | None:
    """Split a ``skill.<name>.<outcome>`` intent id into (skill, outcome, status).

    ``status`` is ``error`` when the skill run failed with a system error
    (outcome ends in ``_error``); denials, No Go, and ``wrong_status`` are
    healthy business outcomes and map to ``ok``. Returns ``None`` for
    non-skill intents.
    """

    if not intent_id:
        return None
    parts = intent_id.split(".")
    if parts[0] != "skill":
        return None
    skill = parts[1] if len(parts) >= 2 else "unknown"
    outcome = parts[2] if len(parts) >= 3 else "unknown"
    status = "error" if outcome.endswith("error") else "ok"
    return skill, outcome, status


def record_skill_outcome(intent_id: str | None) -> None:
    """Emit the mutation-skill funnel counter for a finalized skill response."""

    parsed = parse_skill_intent(intent_id)
    if parsed is None:
        return
    skill, outcome, status = parsed
    record_counter(
        _get_skill_meter(),
        "chat.skill.outcome.count",
        attributes={
            "chat.skill": skill,
            "chat.skill.outcome": outcome,
            "chat.skill.status": status,
        },
    )
