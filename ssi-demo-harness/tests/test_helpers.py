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


def test_payment_operation_enum_values() -> None:
    assert PaymentOperation.CREATE_PAYMENT.value == "create_payment"
