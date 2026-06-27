from ilm.models.enums import LifecycleAction
from ilm.models.instruction_fact import InstructionFact


def test_instruction_fact_from_instruction(sample_subject, sample_instruction) -> None:
    fact = InstructionFact.from_instruction(
        LifecycleAction.APPROVE,
        sample_subject,
        sample_instruction,
        version_number=2,
        authorization={"decision": "allow"},
    )
    assert fact.instruction_id == sample_instruction.instruction_id
    assert fact.version_number == 2
    assert fact.action == "APPROVE"
    assert fact.actor_user_id == sample_subject.user_id
    assert fact.authorization == {"decision": "allow"}
    assert fact.instruction_snapshot["instruction_id"] == sample_instruction.instruction_id
