from __future__ import annotations

from pathlib import Path

import pytest
from chat_application.capabilities import audience_labels, capabilities_for
from chat_application.me.can_create import (
    answer_can_approve_payment,
    answer_can_create_instruction,
    answer_can_create_payment,
)
from chat_application.me.detect import detect_me_intent
from chat_application.me.handlers import try_me_intent
from chat_application.me.my_permissions import answer_my_permissions
from chat_application.me.users_like_me import answer_users_like_me
from chat_application.me.who_am_i import answer_who_am_i
from chat_application.me.who_can_create import answer_who_can_create
from chat_application.subject import Subject


def test_capabilities_for_creator() -> None:
    caps = capabilities_for(
        Subject(user_id="pay-101", title="Ops", roles=["PAYMENT_CREATOR"])
    )
    assert caps.can_create_payment
    assert not caps.can_approve_payment
    assert caps.is_operational
    assert not caps.is_compliance


def test_capabilities_for_dual_role() -> None:
    caps = capabilities_for(
        Subject(
            user_id="pay-203",
            title="VP",
            roles=["PAYMENT_CREATOR", "FUNDING_APPROVER"],
        )
    )
    assert caps.can_create_payment
    assert caps.can_approve_payment
    assert caps.is_operational


def test_audience_labels() -> None:
    assert audience_labels(["PAYMENT_CREATOR", "FUNDING_APPROVER"]) == [
        "payment_creator",
        "funding_approver",
    ]


def test_detect_who_am_i() -> None:
    intent = detect_me_intent("Who am I?")
    assert intent is not None
    assert intent.kind == "who_am_i"


def test_answer_who_am_i() -> None:
    subject = Subject(
        user_id="pay-203",
        given_name="Anna",
        family_name="Kowalski",
        title="Associate",
        roles=["PAYMENT_CREATOR", "FUNDING_APPROVER"],
        groups=["MIDDLE_OFFICE", "UP_TO_100_MILLION_CLUB"],
        covering_lobs=["FX"],
        supervisor_id="pay-201",
    )
    result = answer_who_am_i(subject)
    assert result.intent_id == "me.who_am_i"
    assert "pay-203" in result.answer
    assert "Kowalski, Anna" in result.answer
    assert "PAYMENT_CREATOR" in result.answer
    assert "funding approver" in result.answer


def test_detect_my_permissions() -> None:
    intent = detect_me_intent("What are my permissions?")
    assert intent is not None
    assert intent.kind == "my_permissions"


def test_answer_my_permissions() -> None:
    subject = Subject(
        user_id="pay-101",
        given_name="Emily",
        family_name="Rodriguez",
        title="Analyst",
        roles=["PAYMENT_CREATOR"],
        groups=["MIDDLE_OFFICE", "UP_TO_100_MILLION_CLUB"],
        covering_lobs=["FICC", "FX"],
    )
    result = answer_my_permissions(subject)
    assert result.intent_id == "me.my_permissions"
    assert "Create/update/cancel draft payments" in result.answer
    assert "FICC" in result.answer


def test_detect_users_like_me() -> None:
    intent = detect_me_intent("Are there any other users like me?")
    assert intent is not None
    assert intent.kind == "users_like_me"


def test_detect_who_can_create_for_lob() -> None:
    intent = detect_me_intent("Who can create a payment for LOB FX?")
    assert intent is not None
    assert intent.kind == "who_can_create"
    assert intent.entity_type == "payment"
    assert intent.covering_lob == "FX"


def test_detect_who_can_create_instruction() -> None:
    intent = detect_me_intent("Who can create instructions for LOB FICC?")
    assert intent is not None
    assert intent.kind == "who_can_create"
    assert intent.entity_type == "instruction"
    assert intent.covering_lob == "FICC"


def test_detect_who_covers_lob() -> None:
    intent = detect_me_intent("Who covers LOB FICC?")
    assert intent is not None
    assert intent.kind == "who_covers_lob"
    assert intent.covering_lob == "FICC"


def test_detect_who_can_create_desk_rates() -> None:
    intent = detect_me_intent("Who can create payments for DESK_RATES?")
    assert intent is not None
    assert intent.kind == "who_can_create"
    assert intent.entity_type == "payment"
    assert intent.covering_lob == "DESK_RATES"


def test_me_intent_from_router_remaps_covers_when_create() -> None:
    from chat_application.me.detect import me_intent_from_router
    from chat_application.pipeline.models import RouterDecision

    decision = RouterDecision(path="me", me_kind="who_covers_lob", reasoning="oops")
    intent = me_intent_from_router(decision, "Who can create payments for DESK_RATES?")
    assert intent is not None
    assert intent.kind == "who_can_create"
    assert intent.covering_lob == "DESK_RATES"


def test_answer_who_covers_lob(tmp_path: Path) -> None:
    from chat_application.me.who_covers_lob import answer_who_covers_lob

    users_file = tmp_path / "users.yaml"
    users_file.write_text(
        """
users:
  - user_id: pay-101
    given_name: Emily
    family_name: Rodriguez
    title: Analyst
    roles: [PAYMENT_CREATOR]
    groups: [MIDDLE_OFFICE]
    covering_lobs: [FICC, FX]
  - user_id: fo-ficc-101
    given_name: Ava
    family_name: Chen
    title: Trader
    roles: [INSTRUCTION_SUBMITTER]
    covering_lobs: [FICC]
  - user_id: pay-fx-only
    given_name: Sam
    family_name: Ortiz
    title: Analyst
    roles: [PAYMENT_CREATOR]
    groups: [MIDDLE_OFFICE]
    covering_lobs: [FX]
""",
        encoding="utf-8",
    )
    result = answer_who_covers_lob(covering_lob="FICC", users_file=users_file)
    assert result.intent_id == "me.who_covers_lob"
    assert "FICC" in result.answer
    assert "pay-101" in result.answer
    assert "fo-ficc-101" in result.answer
    assert "pay-fx-only" not in result.answer


def test_answer_who_can_create_for_fx(tmp_path: Path) -> None:
    users_file = tmp_path / "users.yaml"
    users_file.write_text(
        """
users:
  - user_id: pay-101
    given_name: Emily
    family_name: Rodriguez
    title: Analyst
    roles: [PAYMENT_CREATOR]
    groups: [MIDDLE_OFFICE, UP_TO_100_MILLION_CLUB]
    covering_lobs: [FICC, FX]
  - user_id: fo-fx-101
    given_name: Jordan
    family_name: Blake
    title: Analyst
    roles: [PAYMENT_CREATOR]
    lob: FX
  - user_id: pay-201
    given_name: Sophie
    family_name: Laurent
    title: VP
    roles: [FUNDING_APPROVER]
    groups: [MIDDLE_OFFICE, UP_TO_1_BILLION_CLUB]
    covering_lobs: [FICC, FX]
  - user_id: mo-100
    given_name: Sarah
    family_name: Chen
    title: Analyst
    roles: [INSTRUCTION_CREATOR]
    groups: [MIDDLE_OFFICE]
""",
        encoding="utf-8",
    )
    result = answer_who_can_create(
        entity_type="payment",
        covering_lob="FX",
        users_file=users_file,
    )
    assert result.intent_id == "me.who_can_create.payment"
    assert "`pay-101`" in result.answer
    assert "`fo-fx-101`" not in result.answer
    assert "`pay-201`" not in result.answer
    assert "`mo-100`" not in result.answer


def test_answer_who_can_create_instruction(tmp_path: Path) -> None:
    users_file = tmp_path / "users.yaml"
    users_file.write_text(
        """
users:
  - user_id: mo-100
    given_name: Sarah
    family_name: Chen
    title: Analyst
    roles: [INSTRUCTION_CREATOR]
    groups: [MIDDLE_OFFICE]
    supervisor_id: mo-050
  - user_id: pay-101
    given_name: Emily
    family_name: Rodriguez
    title: Analyst
    roles: [PAYMENT_CREATOR]
    groups: [MIDDLE_OFFICE, UP_TO_100_MILLION_CLUB]
    covering_lobs: [FICC, FX]
""",
        encoding="utf-8",
    )
    result = answer_who_can_create(
        entity_type="instruction",
        covering_lob="FICC",
        users_file=users_file,
    )
    assert result.intent_id == "me.who_can_create.instruction"
    assert "`mo-100`" in result.answer
    assert "INSTRUCTION_CREATOR" in result.answer
    assert "`pay-101`" not in result.answer


def test_detect_can_i_create() -> None:
    intent = detect_me_intent("Do I have the permission to create a payment?")
    assert intent is not None
    assert intent.kind == "can_act_on_entity"
    assert intent.action == "CREATE"
    assert intent.entity_type == "payment"


def test_detect_can_i_create_instruction() -> None:
    intent = detect_me_intent("Can I create an instruction?")
    assert intent is not None
    assert intent.kind == "can_act_on_entity"
    assert intent.action == "CREATE"
    assert intent.entity_type == "instruction"


def test_answer_can_create_instruction_no_for_payment_creator() -> None:
    subject = Subject(
        user_id="pay-101",
        given_name="Emily",
        family_name="Rodriguez",
        title="Analyst",
        roles=["PAYMENT_CREATOR"],
        groups=["MIDDLE_OFFICE", "UP_TO_100_MILLION_CLUB"],
        covering_lobs=["FICC", "FX"],
    )
    result = answer_can_create_instruction(subject)
    assert result.intent_id == "me.can_create_instruction.no"
    assert "INSTRUCTION_CREATOR" in result.answer
    assert "PAYMENT_CREATOR" in result.answer


def test_answer_can_create_instruction_yes() -> None:
    subject = Subject(
        user_id="mo-100",
        given_name="Sarah",
        family_name="Chen",
        title="Analyst",
        roles=["INSTRUCTION_CREATOR"],
        groups=["MIDDLE_OFFICE"],
    )
    result = answer_can_create_instruction(subject)
    assert result.intent_id == "me.can_create_instruction.yes"
    assert "**Yes**" in result.answer


def test_answer_can_create_fo_submitter() -> None:
    subject = Subject(
        user_id="fo-fx-101",
        given_name="Jordan",
        family_name="Blake",
        title="Analyst",
        roles=["PAYMENT_CREATOR"],
        lob="FX",
    )
    result = answer_can_create_payment(subject)
    assert result.intent_id == "me.can_create_payment.fo_submitter"
    assert "cannot **create**" in result.answer
    assert "submit" in result.answer.lower()


def test_answer_can_create_middle_office() -> None:
    subject = Subject(
        user_id="pay-101",
        given_name="Emily",
        family_name="Rodriguez",
        title="Analyst",
        roles=["PAYMENT_CREATOR"],
        groups=["MIDDLE_OFFICE", "UP_TO_100_MILLION_CLUB"],
        covering_lobs=["FICC", "FX"],
    )
    result = answer_can_create_payment(subject)
    assert result.intent_id == "me.can_create_payment.yes"
    assert "**Yes**" in result.answer


def test_detect_can_i_approve_generic() -> None:
    intent = detect_me_intent("Can I approve payments?")
    assert intent is not None
    assert intent.kind == "can_act_on_entity"
    assert intent.action == "APPROVE"
    assert intent.entity_id is None


def test_answer_can_approve_yes() -> None:
    subject = Subject(
        user_id="pay-201",
        given_name="Sophie",
        family_name="Laurent",
        title="Vice President",
        roles=["FUNDING_APPROVER"],
        groups=["MIDDLE_OFFICE", "UP_TO_1_BILLION_CLUB"],
        covering_lobs=["FICC", "FX"],
    )
    result = answer_can_approve_payment(subject)
    assert result.intent_id == "me.can_approve_payment.yes"
    assert "**Yes**" in result.answer
    assert "FX" in result.answer


def test_answer_can_approve_no_creator_only() -> None:
    subject = Subject(
        user_id="pay-101",
        title="Analyst",
        roles=["PAYMENT_CREATOR"],
        groups=["MIDDLE_OFFICE", "UP_TO_100_MILLION_CLUB"],
        covering_lobs=["FICC"],
    )
    result = answer_can_approve_payment(subject)
    assert result.intent_id == "me.can_approve_payment.no"
    assert "FUNDING_APPROVER" in result.answer


def test_detect_can_i_approve() -> None:
    intent = detect_me_intent("Do I have permission to approve payment 20260705-FX-P-534?")
    assert intent is not None
    assert intent.kind == "can_act_on_entity"
    assert intent.action == "APPROVE"
    assert intent.entity_id == "20260705-FX-P-534"


def test_detect_waiting_for_me() -> None:
    intent = detect_me_intent("Are there any payments waiting for my approval?")
    assert intent is not None
    assert intent.kind == "waiting_for_me"


@pytest.mark.asyncio
async def test_users_like_me_answer(tmp_path: Path) -> None:
    users_file = tmp_path / "users.yaml"
    users_file.write_text(
        """
users:
  - user_id: pay-101
    given_name: Mina
    family_name: Okonkwo
    title: Payment Ops
    roles: [PAYMENT_CREATOR]
    groups: [MIDDLE_OFFICE]
    covering_lobs: [FICC, FX]
  - user_id: pay-102
    given_name: Luca
    family_name: Bianchi
    title: Payment Ops
    roles: [PAYMENT_CREATOR]
    groups: [MIDDLE_OFFICE]
    covering_lobs: [FICC]
  - user_id: pay-201
    given_name: Sophie
    family_name: Laurent
    title: VP
    roles: [FUNDING_APPROVER]
    groups: [MIDDLE_OFFICE, UP_TO_1_BILLION_CLUB]
    covering_lobs: [FICC]
""",
        encoding="utf-8",
    )
    subject = Subject(
        user_id="pay-101",
        given_name="Mina",
        family_name="Okonkwo",
        title="Payment Ops",
        roles=["PAYMENT_CREATOR"],
        groups=["MIDDLE_OFFICE"],
        covering_lobs=["FICC", "FX"],
    )
    result = answer_users_like_me(subject, users_file=users_file)
    assert result.intent_id == "me.users_like_me"
    assert "pay-102" in result.answer
    assert "pay-101" not in result.answer.split("Closest matches:")[-1]


@pytest.mark.asyncio
async def test_try_me_intent_users_like_me(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    users_file = tmp_path / "users.yaml"
    users_file.write_text(
        """
users:
  - user_id: pay-101
    given_name: Mina
    family_name: Okonkwo
    title: Payment Ops
    roles: [PAYMENT_CREATOR]
    groups: [MIDDLE_OFFICE]
  - user_id: pay-102
    given_name: Luca
    family_name: Bianchi
    title: Payment Ops
    roles: [PAYMENT_CREATOR]
    groups: [MIDDLE_OFFICE]
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("chat_application.me.users_like_me.settings.users_file", users_file)
    subject = Subject(
        user_id="pay-101",
        given_name="Mina",
        family_name="Okonkwo",
        title="Payment Ops",
        roles=["PAYMENT_CREATOR"],
        groups=["MIDDLE_OFFICE"],
    )
    result = await try_me_intent("Are there any other users like me?", subject=subject)
    assert result is not None
    assert "pay-102" in result.answer


@pytest.mark.asyncio
async def test_waiting_for_me_not_approver() -> None:
    subject = Subject(user_id="pay-101", title="Ops", roles=["PAYMENT_CREATOR"])
    result = await try_me_intent(
        "Are there any payments waiting for my approval?",
        subject=subject,
    )
    assert result is not None
    assert "FUNDING_APPROVER" in result.answer


@pytest.mark.asyncio
async def test_try_me_intent_can_create_instruction_not_payment() -> None:
    subject = Subject(
        user_id="pay-101",
        given_name="Emily",
        family_name="Rodriguez",
        title="Analyst",
        roles=["PAYMENT_CREATOR"],
        groups=["MIDDLE_OFFICE", "UP_TO_100_MILLION_CLUB"],
        covering_lobs=["FICC", "FX"],
    )
    result = await try_me_intent("Can I create an instruction?", subject=subject)
    assert result is not None
    assert result.intent_id == "me.can_create_instruction.no"
    assert "**No**" in result.answer
    assert "draft payments" not in result.answer.lower()
