from __future__ import annotations

from enum import StrEnum

from harness.config import Settings
from harness.fixtures import SeedFile, build_instruction_payload, load_users
from harness.ilm_client import InstructionLifecycleClient
from harness.payment_client import PaymentServiceClient
from harness.zitadel_auth import SessionCredentials, ZitadelAuthClient


class Operation(StrEnum):
    CREATE = "create"
    GET = "get"
    LIST = "list"
    SUBMIT = "submit"
    APPROVE = "approve"
    LIST_VERSIONS = "list_versions"


class PaymentOperation(StrEnum):
    CREATE_PAYMENT = "create_payment"
    SUBMIT_PAYMENT = "submit_payment"
    APPROVE_PAYMENT = "approve_payment"
    REJECT_PAYMENT = "reject_payment"


def build_scenario() -> list[tuple[Operation, str, bool, str]]:
    """Return (operation, user_id, expect_success, description)."""
    return [
        (Operation.CREATE, "mo-100", True, "middle office creates FICC instruction"),
        (Operation.GET, "mo-100", True, "creator reads instruction"),
        (Operation.CREATE, "ficc-201", False, "approver cannot create (ALERT)"),
        (Operation.SUBMIT, "mo-100", True, "middle office submits instruction"),
        (Operation.LIST, "mo-100", True, "middle office lists instructions"),
        (Operation.APPROVE, "mo-100", False, "creator cannot approve (ALERT)"),
        (Operation.APPROVE, "ficc-300", True, "FICC VP approves instruction"),
        (Operation.GET, "ficc-300", True, "approver reads instruction"),
        (Operation.LIST_VERSIONS, "fx-201", False, "FX user cannot read FICC versions (ALERT)"),
    ]


def _login_name(user_id: str, email_domain: str) -> str:
    return f"{user_id}@{email_domain}"


def _session_for_user(
    auth: ZitadelAuthClient,
    seed: SeedFile,
    settings: Settings,
    user_id: str,
) -> SessionCredentials:
    password = seed.defaults.get("password", settings.default_password)
    domain = seed.defaults.get("email_domain", settings.email_domain)
    login_name = _login_name(user_id, domain)
    return auth.login(login_name, password)


def _count_security_events(settings: Settings) -> int:
    try:
        from pymongo import MongoClient
    except ImportError:
        return -1

    client = MongoClient(settings.mongodb_uri)
    try:
        collection = client[settings.security_events_database][settings.security_events_collection]
        return collection.count_documents({})
    finally:
        client.close()


def build_seed_plan(count: int) -> list[tuple[str, str, str, str]]:
    """Return (user_id, owning_lob, instruction_type, currency) for each instruction."""
    templates = [
        ("mo-100", "FICC", "SINGLE_USE", "USD"),
        ("mo-101", "FICC", "STANDING", "USD"),
        ("mo-100", "FX", "SINGLE_USE", "EUR"),
        ("mo-101", "FX", "STANDING", "EUR"),
        ("mo-050", "DESK_RATES", "SINGLE_USE", "USD"),
        ("mo-050", "FICC", "SINGLE_USE", "USD"),
        ("mo-010", "FICC", "STANDING", "USD"),
        ("mo-050", "FX", "SINGLE_USE", "GBP"),
    ]
    plan: list[tuple[str, str, str, str]] = []
    for index in range(count):
        plan.append(templates[index % len(templates)])
    return plan


def _approver_for_instruction(owning_lob: str, creator_title: str) -> str | None:
    """Pick a seeded approver that satisfies the OPA approval_matrix for the creator."""
    by_lob: dict[str, dict[str, str]] = {
        "FICC": {
            "Analyst": "ficc-300",
            "Associate": "ficc-300",
            "Vice President": "ficc-400",
            "Managing Director": "ficc-500",
        },
        "FX": {
            "Analyst": "fx-300",
            "Associate": "fx-300",
        },
        "DESK_RATES": {
            "Analyst": "rates-201",
            "Associate": "rates-201",
        },
    }
    lob_key = "DESK_RATES" if owning_lob.startswith("DESK_") else owning_lob
    return by_lob.get(lob_key, {}).get(creator_title)


def _fetch_api_instructions(
    settings: Settings,
    session: SessionCredentials,
    *,
    status: str | None = None,
) -> list[dict]:
    response = ilm_client(settings).list_instructions(session, status=status, limit=500)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, list):
        return payload
    return payload.get("instructions", [])


def auth_client(settings: Settings) -> ZitadelAuthClient:
    return ZitadelAuthClient(
        settings.zitadel_url,
        settings.zitadel_service_pat,
        host_header=settings.zitadel_host_header,
    )


def ilm_client(settings: Settings) -> InstructionLifecycleClient:
    return InstructionLifecycleClient(settings)


def payment_client(settings: Settings) -> PaymentServiceClient:
    return PaymentServiceClient(settings)


# ---------------------------------------------------------------------------
# Payment helpers
# ---------------------------------------------------------------------------

def _fetch_api_payments(
    settings: Settings,
    session: SessionCredentials,
    *,
    status: str | None = None,
) -> list[dict]:
    response = payment_client(settings).list_payments(session, status=status, limit=500)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, list):
        return payload
    return payload.get("payments", [])


def _count_payment_security_events(
    settings: Settings,
    *,
    severity: str | None = None,
    outcome: str | None = None,
) -> int:
    try:
        from pymongo import MongoClient
    except ImportError:
        return -1

    query: dict = {}
    if severity is not None:
        query["severity"] = severity
    if outcome is not None:
        query["event.outcome"] = outcome

    client = MongoClient(settings.mongodb_uri)
    try:
        collection = client[settings.security_events_database][
            settings.payment_security_events_collection
        ]
        return collection.count_documents(query)
    finally:
        client.close()


def _fetch_approved_instructions(
    settings: Settings,
    session: SessionCredentials,
) -> list[dict]:
    """Return STANDING and SINGLE_USE instructions from the ILM REST API."""
    all_instructions = _fetch_api_instructions(settings, session)
    return [
        i for i in all_instructions
        if i.get("status") in {"STANDING", "SINGLE_USE"}
    ]


def build_payment_seed_plan(count: int) -> list[tuple[str, float]]:
    """Return (user_id, amount) for each payment.  Instructions are resolved at run time."""
    templates = [
        ("pay-101", 1_000_000.0),
        ("pay-102", 5_000_000.0),
        ("pay-103", 50_000_000.0),
        ("pay-101", 500_000.0),
        ("pay-102", 10_000_000.0),
        ("pay-103", 100_000_000.0),
        ("pay-101", 2_000_000.0),
        ("pay-102", 750_000.0),
    ]
    plan: list[tuple[str, float]] = []
    for index in range(count):
        plan.append(templates[index % len(templates)])
    return plan


def _universal_payment_approver() -> str:
    """pay-204 covers FICC+FX+DESK_RATES and holds only FUNDING_APPROVER — can never
    self-approve because they cannot create payments."""
    return "pay-204"


def payment_submitter_for_lob(lob: str) -> str:
    """Front-office user who may SUBMIT_PAYMENT for the given instruction LOB."""
    mapping = {
        "FICC": "fo-ficc-101",
        "FX": "fo-fx-101",
        "DESK_RATES": "fo-rates-101",
    }
    if lob not in mapping:
        raise ValueError(f"no front-office payment submitter configured for LOB {lob!r}")
    return mapping[lob]


def build_payment_scenario() -> list[tuple[PaymentOperation, str, bool, str]]:
    """Return (operation, user_id, expect_success, description) for the payment policy demo.

    Full DRAFT → SUBMIT → APPROVE lifecycle with OPA denial cases that emit ALERT events:
      1. pay-101 creates a FICC payment (→ DRAFT, INFO)
      2. pay-201 (approver only) tries to create           → DENY (ALERT)
      3. pay-101 (middle office) tries to submit            → DENY (ALERT)
      4. fo-ficc-101 submits the payment (→ SUBMITTED, INFO)
      5. pay-101 tries to approve own payment               → DENY (ALERT)
      6. pay-203 (FX-only) tries to approve                 → DENY (ALERT)
      7. pay-201 (FICC/FX VP) approves                      → OK (INFO)
    """
    return [
        (PaymentOperation.CREATE_PAYMENT,  "pay-101", True,  "middle office creates FICC payment (→ DRAFT)"),
        (PaymentOperation.CREATE_PAYMENT,  "pay-201", False, "funding approver cannot create payment (ALERT)"),
        (PaymentOperation.SUBMIT_PAYMENT,  "pay-101", False, "middle office cannot submit — not front-office LOB (ALERT)"),
        (PaymentOperation.SUBMIT_PAYMENT,  "fo-ficc-101", True,  "front office submits payment for approval (→ SUBMITTED)"),
        (PaymentOperation.APPROVE_PAYMENT, "pay-101", False, "creator cannot approve own payment (ALERT)"),
        (PaymentOperation.APPROVE_PAYMENT, "pay-203", False, "FX-only approver cannot approve FICC payment (ALERT)"),
        (PaymentOperation.APPROVE_PAYMENT, "pay-201", True,  "FICC/FX VP approver approves payment (→ APPROVED)"),
    ]


__all__ = [
    "Operation",
    "build_instruction_payload",
    "build_scenario",
    "build_seed_plan",
    "_approver_for_instruction",
    "_count_security_events",
    "_count_payment_security_events",
    "_fetch_api_instructions",
    "_fetch_api_payments",
    "_session_for_user",
    "auth_client",
    "ilm_client",
    "load_users",
]
