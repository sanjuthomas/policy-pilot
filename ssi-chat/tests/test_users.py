from __future__ import annotations

from chat_application.auth.users import (
    SeedFile,
    SeedUser,
    chat_users,
    clear_directory_cache,
    compliance_users,
)


def _seed(*users: SeedUser, email_domain: str = "ssi.local") -> SeedFile:
    return SeedFile(defaults={"email_domain": email_domain}, users=list(users))


def test_compliance_users_default_role() -> None:
    seed = _seed(
        SeedUser(
            user_id="comp-001",
            given_name="Alex",
            family_name="Morgan",
            title="Compliance Analyst",
            roles=["COMPLIANCE_ANALYST"],
        ),
        SeedUser(
            user_id="pay-201",
            given_name="Sophie",
            family_name="Laurent",
            title="Vice President",
            roles=["FUNDING_APPROVER"],
        ),
    )
    users = compliance_users(seed=seed)
    assert [user.user_id for user in users] == ["comp-001"]


def test_compliance_users_allowed_roles() -> None:
    seed = _seed(
        SeedUser(
            user_id="comp-001",
            given_name="Alex",
            family_name="Morgan",
            title="Compliance Analyst",
            roles=["COMPLIANCE_ANALYST"],
        ),
        SeedUser(
            user_id="admin-001",
            given_name="Pat",
            family_name="Admin",
            title="Platform Admin",
            roles=["PLATFORM_ADMIN"],
        ),
        SeedUser(
            user_id="pay-201",
            given_name="Sophie",
            family_name="Laurent",
            title="Vice President",
            roles=["FUNDING_APPROVER"],
        ),
    )
    users = compliance_users(
        seed=seed,
        allowed_roles={"COMPLIANCE_ANALYST", "PLATFORM_ADMIN"},
    )
    assert {user.user_id for user in users} == {"comp-001", "admin-001"}


def test_chat_users_includes_audiences() -> None:
    seed = _seed(
        SeedUser(
            user_id="comp-001",
            given_name="Alex",
            family_name="Morgan",
            title="Compliance Analyst",
            roles=["COMPLIANCE_ANALYST"],
        ),
        SeedUser(
            user_id="pay-101",
            given_name="Emily",
            family_name="Rodriguez",
            title="Analyst",
            roles=["PAYMENT_CREATOR"],
            groups=["MIDDLE_OFFICE"],
        ),
        SeedUser(
            user_id="ficc-300",
            given_name="Elena",
            family_name="Vasquez",
            title="Vice President",
            roles=["INSTRUCTION_APPROVER"],
            lob="FICC",
        ),
        SeedUser(
            user_id="svc-chat",
            given_name="Service",
            family_name="Chat",
            title="Service",
            roles=["PAYMENT_CREATOR"],
        ),
    )
    rows = chat_users(
        seed=seed,
        allowed_roles={
            "COMPLIANCE_ANALYST",
            "PAYMENT_CREATOR",
            "INSTRUCTION_APPROVER",
        },
    )
    ids = {row["user_id"] for row in rows}
    assert ids == {"comp-001", "pay-101", "ficc-300"}
    by_id = {row["user_id"]: row for row in rows}
    assert "compliance" in by_id["comp-001"]["audiences"]
    assert "payment_creator" in by_id["pay-101"]["audiences"]
    assert "instruction_approver" in by_id["ficc-300"]["audiences"]


def test_clear_directory_cache() -> None:
    clear_directory_cache()
