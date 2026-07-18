from __future__ import annotations

from harness.helpers import Operation, PaymentOperation, build_scenario, build_seed_plan


def test_build_scenario_has_expected_operations() -> None:
    scenario = build_scenario()
    assert scenario
    operations = {item[0] for item in scenario}
    assert Operation.CREATE in operations
    assert Operation.APPROVE in operations


def test_build_seed_plan_cycles_templates() -> None:
    plan = build_seed_plan(6)
    assert len(plan) == 6
    assert all(len(item) == 4 for item in plan)


def test_build_seed_plan_guarantees_ficc_standing() -> None:
    """Regression context needs an APPROVED FICC STANDING after create+approve."""
    for seed_n in range(50):
        plan = build_seed_plan(3, rng=__import__("random").Random(seed_n))
        assert any(
            owning_lob == "FICC" and instruction_type == "STANDING"
            for _, owning_lob, instruction_type, _ in plan
        ), plan


def test_payment_operation_enum_values() -> None:
    assert PaymentOperation.CREATE_PAYMENT.value == "create_payment"
