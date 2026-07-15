from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from chat_application.rag import RagService


@pytest.fixture
def rag_service() -> RagService:
    return RagService(
        ml_client=MagicMock(),
        vector_search=MagicMock(),
        neo4j=MagicMock(),
    )


@pytest.mark.asyncio
async def test_answer_payment_eligible_approvers_without_token(
    rag_service: RagService,
) -> None:
    answer = await rag_service._answer_payment_eligible_approvers(
        "Who can approve payment abc?",
        bearer_token=None,
        session_id=None,
    )
    assert answer is not None
    assert "Log in as a compliance analyst" in answer


@pytest.mark.asyncio
async def test_answer_payment_eligible_approvers_without_payment_id(
    rag_service: RagService,
) -> None:
    answer = await rag_service._answer_payment_eligible_approvers(
        "Who can approve this payment?",
        bearer_token="token",
        session_id=None,
    )
    assert answer is not None
    assert "payment ID" in answer


@pytest.mark.asyncio
async def test_answer_payment_eligible_approvers_calls_authorization_client(
    rag_service: RagService,
) -> None:
    payment_id = "11111111-1111-1111-1111-111111111111"
    rag_service._eligibility = AsyncMock()
    rag_service._eligibility.eligible_approvers_for_payment.return_value = {
        "payment_id": payment_id,
        "payment_status": "SUBMITTED",
        "amount": 1_000_000,
        "currency": "USD",
        "owning_lob": "FICC",
        "instruction_status": "APPROVED",
        "eligible": [],
        "candidates_evaluated": 1,
    }

    answer = await rag_service._answer_payment_eligible_approvers(
        f"Who can approve payment {payment_id}?",
        bearer_token="token",
        session_id="sess-1",
    )

    assert answer is not None
    assert payment_id in answer
    rag_service._eligibility.eligible_approvers_for_payment.assert_awaited_once()


@pytest.mark.asyncio
async def test_ask_short_circuits_eligibility_question(rag_service: RagService) -> None:
    from chat_application.auth.subject import Subject
    from chat_application.pipeline.models import RouterDecision

    payment_id = "22222222-2222-2222-2222-222222222222"
    rag_service.ml_client.route_query = AsyncMock(
        return_value=RouterDecision(
            path="eligibility",
            strategy="eligibility",
            eligibility_target="payment",
            reasoning="who can approve payment",
        )
    )
    rag_service._eligibility = AsyncMock()
    rag_service._eligibility.eligible_approvers_for_payment.return_value = {
        "payment_id": payment_id,
        "payment_status": "SUBMITTED",
        "amount": 500_000,
        "currency": "USD",
        "owning_lob": "FX",
        "instruction_status": "APPROVED",
        "eligible": [
            {
                "user_id": "pay-201",
                "display_name": "Laurent, Sophie (pay-201)",
                "title": "VP",
                "allow_basis": [],
            }
        ],
        "candidates_evaluated": 1,
    }

    response = await rag_service.ask(
        f"Who can approve payment {payment_id}?",
        [],
        mode="policies",
        bearer_token="token",
        session_id="sess",
        subject=Subject(
            user_id="comp-001",
            title="Compliance Analyst",
            roles=["COMPLIANCE_ANALYST"],
        ),
    )

    assert "Laurent, Sophie" in response.answer
    assert response.sources == []


@pytest.mark.asyncio
async def test_answer_instruction_eligible_approvers_calls_authorization_client(
    rag_service: RagService,
) -> None:
    instruction_id = "11111111-1111-1111-1111-111111111111"
    rag_service._eligibility = AsyncMock()
    rag_service._eligibility.eligible_approvers_for_instruction.return_value = {
        "instruction_id": instruction_id,
        "instruction_status": "SUBMITTED",
        "instruction_type": "STANDING",
        "owning_lob": "FICC",
        "created_by_user_id": "ficc-101",
        "created_by_title": "Analyst",
        "eligible": [
            {
                "user_id": "ficc-300",
                "display_name": "Vasquez, Elena (ficc-300)",
                "title": "Vice President",
                "allow_basis": [],
            }
        ],
        "candidates_evaluated": 4,
    }

    answer = await rag_service._answer_instruction_eligible_approvers(
        f"Who can approve instruction {instruction_id}?",
        bearer_token="token",
        session_id="sess-1",
    )

    assert answer is not None
    assert "Vasquez, Elena" in answer
    rag_service._eligibility.eligible_approvers_for_instruction.assert_awaited_once()


@pytest.mark.asyncio
async def test_ask_short_circuits_instruction_eligibility_question(
    rag_service: RagService,
) -> None:
    from chat_application.auth.subject import Subject
    from chat_application.pipeline.models import RouterDecision

    instruction_id = "22222222-2222-2222-2222-222222222222"
    rag_service.ml_client.route_query = AsyncMock(
        return_value=RouterDecision(
            path="eligibility",
            strategy="eligibility",
            eligibility_target="instruction",
            reasoning="who can approve instruction",
        )
    )
    rag_service._eligibility = AsyncMock()
    rag_service._eligibility.eligible_approvers_for_instruction.return_value = {
        "instruction_id": instruction_id,
        "instruction_status": "SUBMITTED",
        "instruction_type": "STANDING",
        "owning_lob": "FICC",
        "created_by_user_id": "ficc-101",
        "created_by_title": "Analyst",
        "eligible": [],
        "candidates_evaluated": 4,
    }

    response = await rag_service.ask(
        f"Who can approve this instruction {instruction_id}?",
        [],
        mode="policies",
        bearer_token="token",
        session_id="sess",
        subject=Subject(
            user_id="comp-001",
            title="Compliance Analyst",
            roles=["COMPLIANCE_ANALYST"],
        ),
    )

    assert instruction_id in response.answer
    assert response.sources == []


@pytest.mark.asyncio
async def test_ask_policy_directory_uses_distinct_routing_labels(
    rag_service: RagService,
) -> None:
    from chat_application.auth.subject import Subject
    from chat_application.pipeline.models import RouterDecision

    rag_service.ml_client.route_query = AsyncMock(
        return_value=RouterDecision(
            path="policy_directory",
            reasoning="amount club directory",
        )
    )
    rag_service._eligibility = AsyncMock()
    rag_service._eligibility.group_members.return_value = {
        "group": "UP_TO_100_BILLION_CLUB",
        "members": [
            {
                "user_id": "pay-301",
                "display_name": "Chen, Wei (pay-301)",
                "title": "Managing Director",
                "groups": ["UP_TO_100_BILLION_CLUB"],
                "covering_lobs": ["FICC"],
            }
        ],
        "count": 1,
    }

    response = await rag_service.ask(
        "Who has permission to approve payments worth more than $25 billion?",
        [],
        mode="policies",
        bearer_token="token",
        session_id="sess",
        subject=Subject(
            user_id="comp-001",
            title="Compliance Analyst",
            roles=["COMPLIANCE_ANALYST"],
        ),
    )

    assert "Chen, Wei" in response.answer
    assert response.routing is not None
    assert response.routing.path == "policy_directory"
    assert response.routing.answer_synthesis == "policy_directory_api"
    assert response.routing.retrieval_strategy == "policy_directory"
    rag_service._eligibility.group_members.assert_awaited()
