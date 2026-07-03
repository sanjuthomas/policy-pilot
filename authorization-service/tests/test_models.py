from authz.models import PaymentRecord, UserReference


def test_payment_to_opa_payment() -> None:
    payment = PaymentRecord(
        payment_id="p1",
        instruction_id="i1",
        instruction_version=2,
        status="SUBMITTED",
        amount=100.0,
        currency="USD",
        owning_lob="FX",
        created_by=UserReference(user_id="pay-101", supervisor_id="pay-201"),
    )

    payload = payment.to_opa_payment(
        instruction_end_date="2027-01-01",
        instruction_status="APPROVED",
    )

    assert payload["instruction_owning_lob"] == "FX"
    assert payload["created_by"]["user_id"] == "pay-101"
