from datetime import datetime, timedelta

import pytest
from inst.models.api import CreateInstructionRequest
from inst.models.enums import (
    AccountIdentificationScheme,
    FinancialInstitutionIdScheme,
    InstructionType,
    WireScope,
)
from inst.models.instruction import (
    BranchAndFinancialInstitutionIdentification,
    CashAccount,
    CashSettlementInstruction,
    FinancialInstitutionIdentification,
    FundingAccount,
    PartyIdentification,
    UserReference,
)
from pydantic import ValidationError


def test_user_reference_display_name() -> None:
    ref = UserReference(
        user_id="u1",
        given_name="Jane",
        family_name="Doe",
        title="VP",
        roles=["INSTRUCTION_CREATOR"],
    )
    assert ref.display_name == "Doe, Jane (u1)"


def test_user_reference_display_name_without_names() -> None:
    ref = UserReference(user_id="u1", title="VP", roles=["INSTRUCTION_CREATOR"])
    assert ref.display_name == "u1"


def test_to_opa_instruction(sample_instruction: CashSettlementInstruction) -> None:
    opa = sample_instruction.to_opa_instruction()
    assert opa["status"] == "DRAFT"
    assert opa["type"] == "SINGLE_USE"
    assert opa["owning_lob"] == "FICC"
    assert opa["created_by"]["user_id"] == "alice.ficc"
    assert opa["used_by"] is None


def test_funding_account_lob_mismatch_rejected() -> None:
    with pytest.raises(ValidationError, match="funding_account.owning_lob must match"):
        CashSettlementInstruction(
            instruction_type=InstructionType.SINGLE_USE,
            owning_lob="FICC",
            wire_scope=WireScope.DOMESTIC,
            currency="USD",
            funding_account=FundingAccount(
                account_id="a1",
                owning_lob="FX",
            ),
            debtor=PartyIdentification(name="D", postal_address={"country": "US"}),
            debtor_account=CashAccount(
                identification_scheme=AccountIdentificationScheme.PROPRIETARY,
                identification="1",
            ),
            debtor_agent=BranchAndFinancialInstitutionIdentification(
                financial_institution=FinancialInstitutionIdentification(
                    scheme=FinancialInstitutionIdScheme.CLEARING_SYSTEM,
                    identification="021000021",
                    clearing_system_id="USABA",
                )
            ),
            creditor=PartyIdentification(name="C", postal_address={"country": "US"}),
            creditor_account=CashAccount(
                identification_scheme=AccountIdentificationScheme.PROPRIETARY,
                identification="2",
            ),
            creditor_agent=BranchAndFinancialInstitutionIdentification(
                financial_institution=FinancialInstitutionIdentification(
                    scheme=FinancialInstitutionIdScheme.CLEARING_SYSTEM,
                    identification="011401533",
                    clearing_system_id="USABA",
                )
            ),
            charge_bearer="SHAR",
            effective_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            created_by=UserReference(
                user_id="u",
                title="VP",
                roles=["INSTRUCTION_CREATOR"],
            ),
        )


def test_international_wire_requires_bicfi(sample_create_request: CreateInstructionRequest) -> None:
    payload = sample_create_request.model_dump()
    payload["wire_scope"] = "INTERNATIONAL"
    with pytest.raises(ValidationError, match="international wires require BICFI"):
        CreateInstructionRequest.model_validate(payload)


def test_international_wire_valid_bicfi() -> None:
    effective = datetime.utcnow()
    end = effective + timedelta(days=365)
    instruction = CashSettlementInstruction(
        instruction_type=InstructionType.STANDING,
        owning_lob="FX",
        wire_scope=WireScope.INTERNATIONAL,
        currency="EUR",
        funding_account=FundingAccount(account_id="fx-1", owning_lob="FX"),
        debtor=PartyIdentification(name="D", postal_address={"country": "DE"}),
        debtor_account=CashAccount(
            identification_scheme=AccountIdentificationScheme.IBAN,
            identification="DE89370400440532013000",
        ),
        debtor_agent=BranchAndFinancialInstitutionIdentification(
            financial_institution=FinancialInstitutionIdentification(
                scheme=FinancialInstitutionIdScheme.BICFI,
                identification="DEUTDEFF",
            )
        ),
        creditor=PartyIdentification(name="C", postal_address={"country": "GB"}),
        creditor_account=CashAccount(
            identification_scheme=AccountIdentificationScheme.IBAN,
            identification="GB82WEST12345698765432",
        ),
        creditor_agent=BranchAndFinancialInstitutionIdentification(
            financial_institution=FinancialInstitutionIdentification(
                scheme=FinancialInstitutionIdScheme.BICFI,
                identification="WESTGB22",
            )
        ),
        charge_bearer="SHAR",
        effective_date=effective,
        end_date=end,
        created_by=UserReference(
            user_id="u",
            title="VP",
            lob="FX",
            roles=["INSTRUCTION_CREATOR"],
        ),
    )
    assert instruction.wire_scope == WireScope.INTERNATIONAL


def test_domestic_clearing_system_requires_id() -> None:
    effective = datetime.utcnow()
    end = effective + timedelta(days=30)
    with pytest.raises(ValidationError, match="clearing_system_id"):
        CashSettlementInstruction(
            instruction_type=InstructionType.SINGLE_USE,
            owning_lob="FICC",
            wire_scope=WireScope.DOMESTIC,
            currency="USD",
            funding_account=FundingAccount(account_id="a1", owning_lob="FICC"),
            debtor=PartyIdentification(name="D", postal_address={"country": "US"}),
            debtor_account=CashAccount(
                identification_scheme=AccountIdentificationScheme.PROPRIETARY,
                identification="1",
            ),
            debtor_agent=BranchAndFinancialInstitutionIdentification(
                financial_institution=FinancialInstitutionIdentification(
                    scheme=FinancialInstitutionIdScheme.CLEARING_SYSTEM,
                    identification="021000021",
                    clearing_system_id="USABA",
                )
            ),
            creditor=PartyIdentification(name="C", postal_address={"country": "US"}),
            creditor_account=CashAccount(
                identification_scheme=AccountIdentificationScheme.PROPRIETARY,
                identification="2",
            ),
            creditor_agent=BranchAndFinancialInstitutionIdentification(
                financial_institution=FinancialInstitutionIdentification(
                    scheme=FinancialInstitutionIdScheme.CLEARING_SYSTEM,
                    identification="011401533",
                )
            ),
            charge_bearer="SHAR",
            effective_date=effective,
            end_date=end,
            created_by=UserReference(
                user_id="u",
                title="VP",
                lob="FICC",
                roles=["INSTRUCTION_CREATOR"],
            ),
        )
