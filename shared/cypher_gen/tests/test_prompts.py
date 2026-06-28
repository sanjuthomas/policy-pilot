from __future__ import annotations

from cypher_gen.prompts import (
    CYPHER_SYSTEM_PROMPT,
    INSTRUCTION_CYPHER_SYSTEM_PROMPT,
    PAYMENT_CYPHER_SYSTEM_PROMPT,
    SECURITY_EVENTS_CYPHER_SYSTEM_PROMPT,
    cypher_system_prompt,
)


def test_cypher_system_prompt_modes() -> None:
    assert "Payment" in cypher_system_prompt("payments")
    assert "Instruction" in cypher_system_prompt("instructions")
    assert "SecurityEvent" in cypher_system_prompt("events")
    assert cypher_system_prompt("unknown") == CYPHER_SYSTEM_PROMPT


def test_prompt_constants_non_empty() -> None:
    for prompt in (
        CYPHER_SYSTEM_PROMPT,
        INSTRUCTION_CYPHER_SYSTEM_PROMPT,
        PAYMENT_CYPHER_SYSTEM_PROMPT,
        SECURITY_EVENTS_CYPHER_SYSTEM_PROMPT,
    ):
        assert "LIMIT" in prompt
        assert len(prompt) > 100
