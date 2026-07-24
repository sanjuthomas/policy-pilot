from __future__ import annotations

import random
from datetime import date, timedelta

from harness.config import Settings
from harness.fixtures import SeedFile, build_instruction_payload, load_users, user_by_id
from harness.helpers import (
    Operation,
    PaymentOperation,
    _approver_for_instruction,
    _approver_for_payment,
    _count_payment_security_events,
    _eligible_instruction_approvers,
    _fetch_api_instructions,
    _fetch_api_payments,
    _fetch_approved_instructions,
    _instruction_submitter,
    _rejector_for_payment,
    _session_for_user,
    _valid_instruction_seed_pairs,
    auth_client,
    build_payment_scenario,
    build_payment_seed_plan,
    build_scenario,
    build_seed_plan,
    fetch_payment_amount_club_limits,
    instruction_service_client,
    payment_client,
    payment_submitter_for_lob,
    resolve_payment_update_amount,
)
from harness.instruction_client import InstructionServiceClient
from harness.payment_client import PaymentServiceClient
from harness.results import HarnessActionResult
from harness.zitadel_auth import SessionCredentials, ZitadelAuthClient


def _require_pat(settings: Settings) -> str | None:
    if settings.zitadel_service_pat:
        return None
    return "ZITADEL_SERVICE_PAT is required for session login"


def _clients(settings: Settings) -> tuple[SeedFile, ZitadelAuthClient, InstructionServiceClient]:
    seed = load_users(settings)
    auth = auth_client(settings)
    instruction_service = instruction_service_client(settings)
    return seed, auth, instruction_service


def create_instructions(
    settings: Settings,
    count: int,
    _admin_session: SessionCredentials,
) -> HarnessActionResult:
    result = HarnessActionResult(action="create_instructions", requested=count)
    if error := _require_pat(settings):
        result.logs.append(f"error: {error}")
        result.ok = False
        return result

    seed, auth, instruction_service = _clients(settings)
    result.logs.append(f"Creating {count} instruction(s)")

    for index, (user_id, owning_lob, instruction_type, currency) in enumerate(
        build_seed_plan(count, seed=seed), start=1
    ):
        session = _session_for_user(auth, seed, settings, user_id)
        payload = build_instruction_payload(
            owning_lob=owning_lob,
            instruction_type=instruction_type,
            currency=currency,
        )
        result.logs.append(
            f"[{index}] create {instruction_type} {owning_lob} "
            f"currency={currency} user={user_id}"
        )
        response = instruction_service.create_instruction(session, payload)
        if response.status_code == 201:
            result.succeeded += 1
            result.logs.append(f"  -> HTTP 201 created {response.json()['instruction_id']}")
        else:
            result.failed += 1
            result.logs.append(f"  -> HTTP {response.status_code} FAIL")
            detail = response.text.strip()
            if detail:
                result.logs.append(f"     {detail[:300]}")

    result.ok = result.failed == 0
    result.logs.append(
        f"Created {result.succeeded} instruction(s) with {result.failed} failure(s)."
    )
    return result


def submit_instructions(
    settings: Settings,
    count: int,
    admin_session: SessionCredentials,
) -> HarnessActionResult:
    result = HarnessActionResult(action="submit_instructions", requested=count)
    if error := _require_pat(settings):
        result.logs.append(f"error: {error}")
        result.ok = False
        return result

    seed, auth, instruction_service = _clients(settings)
    drafts = _fetch_api_instructions(settings, admin_session, status="DRAFT")
    to_process = drafts[:count]

    if not to_process:
        result.logs.append("No DRAFT instructions available to submit.")
        return result

    submitter_id = _instruction_submitter(seed)
    result.logs.append(f"Submitting up to {len(to_process)} instruction(s) as {submitter_id}")
    submit_session = _session_for_user(auth, seed, settings, submitter_id)

    for index, instruction in enumerate(to_process, start=1):
        instruction_id = instruction["instruction_id"]
        result.logs.append(
            f"[{index}] {instruction_id} lob={instruction['owning_lob']} status=DRAFT"
        )
        response = instruction_service.submit_instruction(submit_session, instruction_id)
        if response.status_code in range(200, 300):
            result.succeeded += 1
            result.logs.append(f"  -> submit HTTP {response.status_code} OK")
        else:
            result.failed += 1
            result.logs.append(f"  -> submit HTTP {response.status_code} FAIL")
            detail = response.text.strip()
            if detail:
                result.logs.append(f"     {detail[:300]}")

    result.ok = result.failed == 0
    result.logs.append(
        f"Submitted {result.succeeded} instruction(s) with {result.failed} failure(s)."
    )
    return result


def approve_instructions(
    settings: Settings,
    count: int,
    admin_session: SessionCredentials,
) -> HarnessActionResult:
    result = HarnessActionResult(action="approve_instructions", requested=count)
    if error := _require_pat(settings):
        result.logs.append(f"error: {error}")
        result.ok = False
        return result

    seed, auth, instruction_service = _clients(settings)
    submitter_id = _instruction_submitter(seed)

    drafts = _fetch_api_instructions(settings, admin_session, status="DRAFT")
    submitted = _fetch_api_instructions(settings, admin_session, status="SUBMITTED")
    candidates = drafts + submitted
    if not candidates:
        result.logs.append("No DRAFT or SUBMITTED instructions available to approve.")
        return result

    def _created_by(instruction: dict) -> dict:
        return instruction.get("created_by") or {}

    def _sort_key(instruction: dict) -> tuple[int, int, str]:
        created_by = _created_by(instruction)
        approvable = _approver_for_instruction(
            seed,
            instruction["owning_lob"],
            str(created_by.get("user_id") or ""),
            str(created_by.get("title") or ""),
            created_by.get("supervisor_id"),
        )
        # Prefer FICC STANDING so regression context gets ficc_standing_instruction_id.
        is_ficc_standing = (
            instruction.get("owning_lob") == "FICC"
            and instruction.get("instruction_type") == "STANDING"
        )
        return (
            0 if approvable else 1,
            0 if is_ficc_standing else 1,
            instruction["instruction_id"],
        )

    candidates.sort(key=_sort_key)
    to_process = candidates[:count]
    result.logs.append(f"Approving up to {len(to_process)} instruction(s)")

    for index, instruction in enumerate(to_process, start=1):
        instruction_id = instruction["instruction_id"]
        owning_lob = instruction["owning_lob"]
        status = instruction["status"]
        created_by = _created_by(instruction)
        creator_title = created_by.get("title", "")
        creator_id = created_by.get("user_id", "")
        approver_id = _approver_for_instruction(
            seed,
            owning_lob,
            str(creator_id or ""),
            str(creator_title or ""),
            created_by.get("supervisor_id"),
        )
        if not approver_id:
            result.skipped += 1
            result.failed += 1
            result.logs.append(
                f"[{index}] {instruction_id} skip: no eligible approver for "
                f"lob={owning_lob} creator={creator_id} title={creator_title!r}"
            )
            continue

        result.logs.append(
            f"[{index}] {instruction_id} lob={owning_lob} status={status} "
            f"creator={creator_id} title={creator_title} "
            f"submit={submitter_id} approve={approver_id}"
        )

        if status == "DRAFT":
            submit_session = _session_for_user(auth, seed, settings, submitter_id)
            submit_response = instruction_service.submit_instruction(submit_session, instruction_id)
            if submit_response.status_code not in range(200, 300):
                result.failed += 1
                result.logs.append(f"  -> submit HTTP {submit_response.status_code} FAIL")
                detail = submit_response.text.strip()
                if detail:
                    result.logs.append(f"     {detail[:300]}")
                continue
            result.logs.append(f"  -> submit HTTP {submit_response.status_code} OK")

        approve_session = _session_for_user(auth, seed, settings, approver_id)
        approve_response = instruction_service.approve_instruction(approve_session, instruction_id)
        if approve_response.status_code in range(200, 300):
            result.succeeded += 1
            final_status = approve_response.json().get("status", "APPROVED")
            result.logs.append(f"  -> approve HTTP {approve_response.status_code} OK ({final_status})")
        else:
            result.failed += 1
            result.logs.append(f"  -> approve HTTP {approve_response.status_code} FAIL")
            detail = approve_response.text.strip()
            if detail:
                result.logs.append(f"     {detail[:300]}")

    result.ok = result.failed == 0
    result.logs.append(
        f"Approved {result.succeeded} instruction(s) with {result.failed} failure(s)."
    )
    return result


def reject_instructions(
    settings: Settings,
    count: int,
    admin_session: SessionCredentials,
) -> HarnessActionResult:
    result = HarnessActionResult(action="reject_instructions", requested=count)
    if error := _require_pat(settings):
        result.logs.append(f"error: {error}")
        result.ok = False
        return result

    seed, auth, instruction_service = _clients(settings)
    submitted = _fetch_api_instructions(settings, admin_session, status="SUBMITTED")
    to_process = submitted[:count]

    if not to_process:
        result.logs.append("No SUBMITTED instructions available to reject.")
        return result

    result.logs.append(f"Rejecting up to {len(to_process)} instruction(s)")

    for index, instruction in enumerate(to_process, start=1):
        instruction_id = instruction["instruction_id"]
        owning_lob = instruction["owning_lob"]
        created_by = instruction.get("created_by") or {}
        creator_title = created_by.get("title", "")
        creator_id = created_by.get("user_id", "")
        approver_id = _approver_for_instruction(
            seed,
            owning_lob,
            str(creator_id or ""),
            str(creator_title or ""),
            created_by.get("supervisor_id"),
        )
        if not approver_id:
            result.skipped += 1
            result.failed += 1
            result.logs.append(
                f"[{index}] {instruction_id} skip: no eligible approver for "
                f"lob={owning_lob} creator={creator_id}"
            )
            continue

        result.logs.append(
            f"[{index}] {instruction_id} lob={owning_lob} reject as {approver_id}"
        )
        session = _session_for_user(auth, seed, settings, approver_id)
        response = instruction_service.reject_instruction(
            session,
            instruction_id,
            reason="Rejected via test harness UI",
        )
        if response.status_code in range(200, 300):
            result.succeeded += 1
            result.logs.append(f"  -> reject HTTP {response.status_code} OK")
        else:
            result.failed += 1
            result.logs.append(f"  -> reject HTTP {response.status_code} FAIL")
            detail = response.text.strip()
            if detail:
                result.logs.append(f"     {detail[:300]}")

    result.ok = result.failed == 0
    result.logs.append(
        f"Rejected {result.succeeded} instruction(s) with {result.failed} failure(s)."
    )
    return result


def run_policy_scenario(
    settings: Settings,
    _admin_session: SessionCredentials,
) -> HarnessActionResult:
    result = HarnessActionResult(action="run_policy_scenario", requested=1)
    if error := _require_pat(settings):
        result.logs.append(f"error: {error}")
        result.ok = False
        return result

    seed, auth, instruction_service = _clients(settings)
    instruction_id: str | None = None
    failures = 0

    result.logs.append("Running instruction lifecycle policy scenario")

    for index, (operation, user_id, expect_success, description) in enumerate(build_scenario()):
        session = _session_for_user(auth, seed, settings, user_id)
        result.logs.append(
            f"[{index + 1}] {description} "
            f"(user={user_id}, op={operation.value}, expect={'OK' if expect_success else 'DENY'})"
        )

        if operation == Operation.CREATE:
            response = instruction_service.create_instruction(session, build_instruction_payload(owning_lob="FICC"))
            if expect_success and response.status_code == 201:
                instruction_id = response.json()["instruction_id"]
        elif operation == Operation.GET:
            if not instruction_id:
                result.logs.append("  skip: no instruction_id")
                continue
            response = instruction_service.get_instruction(session, instruction_id)
        elif operation == Operation.LIST:
            response = instruction_service.list_instructions(session)
        elif operation == Operation.SUBMIT:
            if not instruction_id:
                result.logs.append("  skip: no instruction_id")
                continue
            response = instruction_service.submit_instruction(session, instruction_id)
        elif operation == Operation.APPROVE:
            if not instruction_id:
                result.logs.append("  skip: no instruction_id")
                continue
            response = instruction_service.approve_instruction(session, instruction_id)
        elif operation == Operation.LIST_VERSIONS:
            if not instruction_id:
                result.logs.append("  skip: no instruction_id")
                continue
            response = instruction_service.list_versions(session, instruction_id)
        else:
            raise RuntimeError(f"unsupported operation: {operation}")

        ok = (200 <= response.status_code < 300) == expect_success
        result.logs.append(f"  -> HTTP {response.status_code} {'PASS' if ok else 'FAIL'}")
        if not ok:
            failures += 1
            detail = response.text.strip()
            if detail:
                result.logs.append(f"     {detail[:300]}")

    result.succeeded = 1 if failures == 0 else 0
    result.failed = failures
    result.ok = failures == 0
    result.logs.append(f"Scenario finished with {failures} failure(s).")
    return result


# ---------------------------------------------------------------------------
# Payment actions
# ---------------------------------------------------------------------------

def _payment_clients(
    settings: Settings,
) -> tuple[SeedFile, ZitadelAuthClient, PaymentServiceClient]:
    seed = load_users(settings)
    auth = auth_client(settings)
    ps = payment_client(settings)
    return seed, auth, ps


def create_payments(
    settings: Settings,
    count: int,
    admin_session: SessionCredentials,
) -> HarnessActionResult:
    result = HarnessActionResult(action="create_payments", requested=count)
    if error := _require_pat(settings):
        result.logs.append(f"error: {error}")
        result.ok = False
        return result

    seed, auth, ps = _payment_clients(settings)

    approved = _fetch_approved_instructions(settings, admin_session)
    # Prefer STANDING type so we can reuse them; fall back to all APPROVED.
    standing = [i for i in approved if i.get("instruction_type") == "STANDING"]
    pool = standing if standing else approved

    if not pool:
        result.logs.append(
            "No APPROVED instructions found. "
            "Run approve-instructions first."
        )
        result.ok = False
        return result

    try:
        club_limits = fetch_payment_amount_club_limits(settings, admin_session)
    except Exception as exc:
        result.logs.append(f"error: could not load OPA amount club limits: {exc}")
        result.ok = False
        return result

    value_date = (date.today() + timedelta(days=1)).isoformat()
    result.logs.append(
        f"Creating {count} payment(s) against {len(pool)} approved instruction(s)"
    )

    for index, (user_id, amount) in enumerate(
        build_payment_seed_plan(count, seed=seed, club_limits=club_limits), start=1
    ):
        try:
            creator = user_by_id(seed, user_id)
        except KeyError:
            result.failed += 1
            result.logs.append(f"[{index}] skip: unknown payment creator {user_id}")
            continue

        matching = [
            instruction
            for instruction in pool
            if instruction.get("owning_lob") in creator.covering_lobs
        ]
        if not matching:
            result.failed += 1
            result.logs.append(
                f"[{index}] skip: no approved instruction for creator {user_id} "
                f"covering {creator.covering_lobs}"
            )
            continue

        instruction = matching[index % len(matching)]
        instruction_id = instruction["instruction_id"]
        owning_lob = instruction.get("owning_lob", "?")

        result.logs.append(
            f"[{index}] create payment  user={user_id}  amount={amount:,.0f}"
            f"  lob={owning_lob}  instruction={instruction_id[:8]}…"
        )
        session = _session_for_user(auth, seed, settings, user_id)
        response = ps.create_payment(session, instruction_id, amount, value_date)

        if response.status_code == 201:
            result.succeeded += 1
            result.logs.append(
                f"  -> HTTP 201 created {response.json()['payment_id']}"
            )
        else:
            result.failed += 1
            result.logs.append(f"  -> HTTP {response.status_code} FAIL")
            detail = response.text.strip()
            if detail:
                result.logs.append(f"     {detail[:300]}")

    result.ok = result.failed == 0
    result.logs.append(
        f"Created {result.succeeded} payment(s) with {result.failed} failure(s)."
    )
    return result


def submit_payments(
    settings: Settings,
    count: int,
    admin_session: SessionCredentials,
) -> HarnessActionResult:
    result = HarnessActionResult(action="submit_payments", requested=count)
    if error := _require_pat(settings):
        result.logs.append(f"error: {error}")
        result.ok = False
        return result

    seed, auth, ps = _payment_clients(settings)

    drafts = _fetch_api_payments(settings, admin_session, status="DRAFT")
    to_process = drafts[:count]

    if not to_process:
        result.logs.append("No DRAFT payments available to submit.")
        return result

    result.logs.append(f"Submitting up to {len(to_process)} payment(s)")

    for index, payment in enumerate(to_process, start=1):
        payment_id = payment["payment_id"]
        owning_lob = payment.get("owning_lob", "?")
        try:
            submitter_id = payment_submitter_for_lob(seed, owning_lob)
        except ValueError as exc:
            result.failed += 1
            result.logs.append(f"[{index}] {payment_id}  lob={owning_lob}  skip: {exc}")
            continue
        result.logs.append(
            f"[{index}] {payment_id}  lob={owning_lob}  submitting as {submitter_id}"
        )
        session = _session_for_user(auth, seed, settings, submitter_id)
        response = ps.submit_payment(session, payment_id)
        if response.status_code in range(200, 300):
            result.succeeded += 1
            result.logs.append(f"  -> submit HTTP {response.status_code} OK")
        else:
            result.failed += 1
            result.logs.append(f"  -> submit HTTP {response.status_code} FAIL")
            detail = response.text.strip()
            if detail:
                result.logs.append(f"     {detail[:300]}")

    result.ok = result.failed == 0
    result.logs.append(
        f"Submitted {result.succeeded} payment(s) with {result.failed} failure(s)."
    )
    return result


def update_payments(
    settings: Settings,
    count: int,
    admin_session: SessionCredentials,
    *,
    amount: float | None = None,
) -> HarnessActionResult:
    result = HarnessActionResult(action="update_payments", requested=count)
    if error := _require_pat(settings):
        result.logs.append(f"error: {error}")
        result.ok = False
        return result

    seed, auth, ps = _payment_clients(settings)

    drafts = _fetch_api_payments(settings, admin_session, status="DRAFT")
    to_process = drafts[:count]

    if not to_process:
        result.logs.append("No DRAFT payments available to update.")
        return result

    amount_note = f"amount={amount:,.0f}" if amount else "auto amount bump"
    result.logs.append(f"Updating up to {len(to_process)} DRAFT payment(s) ({amount_note})")

    try:
        club_limits = fetch_payment_amount_club_limits(settings, admin_session)
    except Exception as exc:
        result.logs.append(f"error: could not load OPA amount club limits: {exc}")
        result.ok = False
        return result

    for index, payment in enumerate(to_process, start=1):
        payment_id = payment["payment_id"]
        instruction_id = payment.get("instruction_id", "")
        value_date = payment.get("value_date", "2026-07-01")
        current_amount = float(payment.get("amount") or 0)
        created_by = payment.get("created_by") or {}
        creator_id = created_by.get("user_id")
        if not creator_id:
            result.failed += 1
            result.logs.append(f"[{index}] {payment_id} skip: missing created_by")
            continue

        new_amount = resolve_payment_update_amount(
            current_amount,
            creator_id,
            seed=seed,
            club_limits=club_limits,
            override=amount,
        )
        if new_amount == current_amount:
            result.skipped += 1
            result.logs.append(
                f"[{index}] {payment_id} skip: amount unchanged at {current_amount:,.0f}"
            )
            continue

        result.logs.append(
            f"[{index}] {payment_id}  user={creator_id}  "
            f"{current_amount:,.0f} -> {new_amount:,.0f}"
        )
        session = _session_for_user(auth, seed, settings, creator_id)
        response = ps.update_payment(
            session,
            payment_id,
            instruction_id,
            new_amount,
            value_date,
        )
        if response.status_code in range(200, 300):
            result.succeeded += 1
            body = response.json()
            result.logs.append(
                f"  -> HTTP {response.status_code} v{body.get('version_number', '?')} "
                f"amount={body.get('amount', new_amount):,.0f}"
            )
        else:
            result.failed += 1
            result.logs.append(f"  -> update HTTP {response.status_code} FAIL")
            detail = response.text.strip()
            if detail:
                result.logs.append(f"     {detail[:300]}")

    result.ok = result.failed == 0
    result.logs.append(
        f"Updated {result.succeeded} payment(s) with {result.failed} failure(s), "
        f"{result.skipped} skipped."
    )
    return result


def approve_payments(
    settings: Settings,
    count: int,
    admin_session: SessionCredentials,
) -> HarnessActionResult:
    result = HarnessActionResult(action="approve_payments", requested=count)
    if error := _require_pat(settings):
        result.logs.append(f"error: {error}")
        result.ok = False
        return result

    seed, auth, ps = _payment_clients(settings)

    submitted = _fetch_api_payments(settings, admin_session, status="SUBMITTED")
    if not submitted:
        result.logs.append("No SUBMITTED payments available to approve.")
        return result

    try:
        club_limits = fetch_payment_amount_club_limits(settings, admin_session)
    except Exception as exc:
        result.logs.append(f"error: could not load OPA amount club limits: {exc}")
        result.ok = False
        return result

    def _sort_key(payment: dict) -> tuple[int, str]:
        approvable = _approver_for_payment(seed, payment, club_limits=club_limits)
        return (0 if approvable else 1, payment["payment_id"])

    to_process = sorted(submitted, key=_sort_key)[:count]
    result.logs.append(f"Approving up to {len(to_process)} payment(s)")

    for index, payment in enumerate(to_process, start=1):
        payment_id = payment["payment_id"]
        amount = payment.get("amount", 0)
        owning_lob = payment.get("owning_lob", "?")
        created_by = payment.get("created_by") or {}
        creator_id = created_by.get("user_id", "?")
        approver_id = _approver_for_payment(seed, payment, club_limits=club_limits)
        if not approver_id:
            result.skipped += 1
            result.failed += 1
            result.logs.append(
                f"[{index}] {payment_id} skip: no eligible approver for "
                f"lob={owning_lob} creator={creator_id} amount={amount:,.0f}"
            )
            continue

        result.logs.append(
            f"[{index}] {payment_id} lob={owning_lob} creator={creator_id} "
            f"amount={amount:,.0f} approve={approver_id}"
        )
        approve_session = _session_for_user(auth, seed, settings, approver_id)
        response = ps.approve_payment(approve_session, payment_id)
        if response.status_code in range(200, 300):
            result.succeeded += 1
            result.logs.append(f"  -> approve HTTP {response.status_code} OK")
        else:
            result.failed += 1
            result.logs.append(f"  -> approve HTTP {response.status_code} FAIL")
            detail = response.text.strip()
            if detail:
                result.logs.append(f"     {detail[:300]}")

    result.ok = result.failed == 0
    result.logs.append(
        f"Approved {result.succeeded} payment(s) with {result.failed} failure(s)."
    )
    return result


def reject_payments(
    settings: Settings,
    count: int,
    admin_session: SessionCredentials,
) -> HarnessActionResult:
    result = HarnessActionResult(action="reject_payments", requested=count)
    if error := _require_pat(settings):
        result.logs.append(f"error: {error}")
        result.ok = False
        return result

    seed, auth, ps = _payment_clients(settings)

    submitted = _fetch_api_payments(settings, admin_session, status="SUBMITTED")
    to_process = submitted[:count]

    if not to_process:
        result.logs.append("No SUBMITTED payments available to reject.")
        return result

    result.logs.append(f"Rejecting up to {len(to_process)} payment(s)")

    for index, payment in enumerate(to_process, start=1):
        payment_id = payment["payment_id"]
        owning_lob = payment.get("owning_lob", "?")
        rejector_id = _rejector_for_payment(seed, payment)
        if not rejector_id:
            result.skipped += 1
            result.failed += 1
            result.logs.append(
                f"[{index}] {payment_id} skip: no eligible rejector for lob={owning_lob}"
            )
            continue

        result.logs.append(f"[{index}] {payment_id} lob={owning_lob} reject={rejector_id}")
        reject_session = _session_for_user(auth, seed, settings, rejector_id)
        response = ps.reject_payment(
            reject_session, payment_id, reason="Rejected via test harness"
        )
        if response.status_code in range(200, 300):
            result.succeeded += 1
            result.logs.append(f"  -> reject HTTP {response.status_code} OK")
        else:
            result.failed += 1
            result.logs.append(f"  -> reject HTTP {response.status_code} FAIL")
            detail = response.text.strip()
            if detail:
                result.logs.append(f"     {detail[:300]}")

    result.ok = result.failed == 0
    result.logs.append(
        f"Rejected {result.succeeded} payment(s) with {result.failed} failure(s)."
    )
    return result


def run_payment_policy_scenario(
    settings: Settings,
    admin_session: SessionCredentials,
) -> HarnessActionResult:
    """OPA payment policy scenario with expected INFO and ALERT security events.

    Creates a payment, exercises CREATE/SUBMIT/APPROVE denials (ALERT), then
    completes the happy path (INFO).
    """
    result = HarnessActionResult(action="run_payment_policy_scenario", requested=1)
    if error := _require_pat(settings):
        result.logs.append(f"error: {error}")
        result.ok = False
        return result

    seed, auth, ps = _payment_clients(settings)
    failures = 0
    scenario = build_payment_scenario()
    expected_denials = sum(1 for _, _, expect_success, _ in scenario if not expect_success)
    # pay-203 APPROVE fails on OBO instruction VIEW before payment policy, so one
    # HTTP DENY does not create a payment ALERT (instruction ALERT instead).
    expected_payment_alerts = expected_denials - 1
    expected_successes = sum(1 for _, _, expect_success, _ in scenario if expect_success)

    alerts_before = (
        _count_payment_security_events(settings, severity="ALERT", outcome="failure")
        if settings.verify_security_events
        else -1
    )
    infos_before = (
        _count_payment_security_events(settings, severity="INFO", outcome="success")
        if settings.verify_security_events
        else -1
    )

    result.logs.append("Running payment lifecycle policy scenario")

    # Discover a FICC approved instruction to use throughout the scenario
    approved = _fetch_approved_instructions(settings, admin_session)
    ficc_instructions = [
        i for i in approved
        if i.get("owning_lob") == "FICC"
        and i.get("instruction_type") == "STANDING"
    ]
    if not ficc_instructions:
        ficc_instructions = [i for i in approved if i.get("owning_lob") == "FICC"]
    if not ficc_instructions:
        result.logs.append(
            "No approved FICC instruction found. "
            "Run approve-instructions first to seed at least one FICC instruction."
        )
        result.ok = False
        return result

    instruction_id = ficc_instructions[0]["instruction_id"]
    value_date = (date.today() + timedelta(days=1)).isoformat()
    result.logs.append(f"Using FICC instruction {instruction_id}")

    payment_id: str | None = None

    for index, (operation, user_id, expect_success, description) in enumerate(
        scenario, start=1
    ):
        session = _session_for_user(auth, seed, settings, user_id)
        result.logs.append(
            f"[{index}] {description} "
            f"(user={user_id}, op={operation.value}, expect={'OK' if expect_success else 'DENY'})"
        )

        if operation == PaymentOperation.CREATE_PAYMENT:
            response = ps.create_payment(session, instruction_id, 1_000_000.0, value_date)
            if expect_success and response.status_code == 201:
                payment_id = response.json()["payment_id"]
        elif operation == PaymentOperation.SUBMIT_PAYMENT:
            if not payment_id:
                result.logs.append("  skip: no payment_id (earlier CREATE failed)")
                continue
            response = ps.submit_payment(session, payment_id)
        elif operation == PaymentOperation.APPROVE_PAYMENT:
            if not payment_id:
                result.logs.append("  skip: no payment_id (earlier step failed)")
                continue
            response = ps.approve_payment(session, payment_id)
        else:
            raise RuntimeError(f"unsupported operation: {operation}")

        ok = (200 <= response.status_code < 300) == expect_success
        result.logs.append(f"  -> HTTP {response.status_code} {'PASS' if ok else 'FAIL'}")
        if not ok:
            failures += 1
            detail = response.text.strip()
            if detail:
                result.logs.append(f"     {detail[:300]}")

    if settings.verify_security_events and alerts_before >= 0:
        alerts_after = _count_payment_security_events(
            settings, severity="ALERT", outcome="failure"
        )
        infos_after = _count_payment_security_events(
            settings, severity="INFO", outcome="success"
        )
        new_alerts = alerts_after - alerts_before
        new_infos = infos_after - infos_before
        result.logs.append(
            f"Security events: +{new_alerts} payment ALERT "
            f"(expected {expected_payment_alerts}; "
            f"{expected_denials} HTTP denials incl. instruction VIEW spillover), "
            f"+{new_infos} INFO (expected {expected_successes})"
        )
        if new_alerts < expected_payment_alerts:
            failures += 1
            result.logs.append(
                "  FAIL: expected a payment ALERT for each payment-policy denial "
                "(excluding pay-203 instruction VIEW spillover)"
            )
        if new_infos < expected_successes:
            failures += 1
            result.logs.append(
                "  FAIL: expected an INFO security event for each authorized action"
            )

    result.succeeded = 1 if failures == 0 else 0
    result.failed = failures
    result.ok = failures == 0
    result.logs.append(f"Scenario finished with {failures} failure(s).")
    return result


def _ficc_payment_creator(seed: SeedFile) -> str | None:
    """Deterministic middle-office PAYMENT_CREATOR covering FICC (e.g. pay-101)."""
    candidates = sorted(
        user.user_id
        for user in seed.users
        if "PAYMENT_CREATOR" in user.roles
        and "MIDDLE_OFFICE" in user.groups
        and "FICC" in user.covering_lobs
    )
    return candidates[0] if candidates else None


def _ficc_instruction_suspender(seed: SeedFile) -> str | None:
    """OPA SUSPEND requires INSTRUCTION_APPROVER + Managing Director + same LOB."""
    candidates = sorted(
        user.user_id
        for user in seed.users
        if "INSTRUCTION_APPROVER" in user.roles
        and user.lob == "FICC"
        and user.title == "Managing Director"
    )
    return candidates[0] if candidates else None


def _create_approved_ficc_instruction(
    settings: Settings,
    *,
    seed: SeedFile,
    auth: ZitadelAuthClient,
    instruction_service: InstructionServiceClient,
    result: HarnessActionResult,
    instruction_type: str = "STANDING",
) -> str | None:
    """Create → submit → approve a FICC instruction. Returns id or None."""
    ficc_creators = sorted(
        creator_id
        for creator_id, owning_lob in _valid_instruction_seed_pairs(seed)
        if owning_lob == "FICC"
    )
    if not ficc_creators:
        result.logs.append("error: no eligible FICC instruction creator in directory")
        return None

    creator_id = ficc_creators[0]
    creator = user_by_id(seed, creator_id)
    approvers = _eligible_instruction_approvers(
        seed,
        owning_lob="FICC",
        creator_user_id=creator_id,
        creator_title=creator.title,
        creator_supervisor_id=creator.supervisor_id,
    )
    if not approvers:
        result.logs.append(f"error: no eligible FICC approver for creator {creator_id}")
        return None
    approver_id = sorted(approvers)[0]

    creator_session = _session_for_user(auth, seed, settings, creator_id)
    payload = build_instruction_payload(
        owning_lob="FICC", instruction_type=instruction_type
    )
    result.logs.append(f"create FICC {instruction_type} instruction as {creator_id}")
    response = instruction_service.create_instruction(creator_session, payload)
    if response.status_code != 201:
        result.logs.append(f"  -> create instruction HTTP {response.status_code} FAIL")
        result.logs.append(f"     {response.text.strip()[:300]}")
        return None
    instruction_id = response.json()["instruction_id"]
    result.logs.append(f"  -> HTTP 201 {instruction_id}")

    result.logs.append(f"submit instruction {instruction_id} as {creator_id}")
    response = instruction_service.submit_instruction(creator_session, instruction_id)
    if response.status_code not in range(200, 300):
        result.logs.append(f"  -> submit HTTP {response.status_code} FAIL")
        result.logs.append(f"     {response.text.strip()[:300]}")
        return None

    approver_session = _session_for_user(auth, seed, settings, approver_id)
    result.logs.append(f"approve instruction {instruction_id} as {approver_id}")
    response = instruction_service.approve_instruction(approver_session, instruction_id)
    if response.status_code not in range(200, 300):
        result.logs.append(f"  -> approve HTTP {response.status_code} FAIL")
        result.logs.append(f"     {response.text.strip()[:300]}")
        return None

    if instruction_type == "STANDING":
        result.context["ficc_standing_instruction_id"] = instruction_id
    result.context["skill_fixture_instruction_creator"] = creator_id
    suspender = _ficc_instruction_suspender(seed)
    if suspender:
        result.context["skill_fixture_instruction_suspender"] = suspender
    return instruction_id


def _create_approved_ficc_standing(
    settings: Settings,
    *,
    seed: SeedFile,
    auth: ZitadelAuthClient,
    instruction_service: InstructionServiceClient,
    result: HarnessActionResult,
) -> str | None:
    """Create → submit → approve a FICC STANDING instruction. Returns id or None."""
    return _create_approved_ficc_instruction(
        settings,
        seed=seed,
        auth=auth,
        instruction_service=instruction_service,
        result=result,
        instruction_type="STANDING",
    )


_SKILL_FIXTURE_NEEDS = frozenset(
    {"instruction", "draft", "submitted", "suspended", "used_single_use"}
)


def setup_skill_fixture(
    settings: Settings,
    admin_session: SessionCredentials,
    *,
    need: str = "instruction",
) -> HarnessActionResult:
    """Per-case setup for chat mutation-skill regressions.

    ``need`` selects how far to build the isolated fixture chain:
      - ``instruction`` — approved FICC STANDING instruction
      - ``draft`` — that instruction + a DRAFT payment
      - ``submitted`` — that instruction + a SUBMITTED payment
      - ``suspended`` — approved FICC STANDING then SUSPENDED
      - ``used_single_use`` — approved FICC SINGLE_USE consumed by a submitted payment

    Returns concrete ids in ``result.context``. Pair with
    :func:`teardown_skill_fixture` so each skill case is independent.
    """
    if need not in _SKILL_FIXTURE_NEEDS:
        result = HarnessActionResult(action="setup_skill_fixture", requested=1, ok=False)
        result.logs.append(
            "error: need must be "
            "instruction|draft|submitted|suspended|used_single_use, "
            f"got {need!r}"
        )
        return result

    requested = {
        "instruction": 1,
        "draft": 2,
        "submitted": 2,
        "suspended": 2,
        "used_single_use": 2,
    }[need]
    result = HarnessActionResult(action="setup_skill_fixture", requested=requested)
    if error := _require_pat(settings):
        result.logs.append(f"error: {error}")
        result.ok = False
        return result

    seed, auth, instruction_service = _clients(settings)
    instruction_type = "SINGLE_USE" if need == "used_single_use" else "STANDING"
    instruction_id = _create_approved_ficc_instruction(
        settings,
        seed=seed,
        auth=auth,
        instruction_service=instruction_service,
        result=result,
        instruction_type=instruction_type,
    )
    if not instruction_id:
        result.failed += 1
        result.ok = False
        return result
    result.succeeded += 1

    if need == "instruction":
        result.ok = True
        result.logs.append(f"Skill fixture ready (instruction): {instruction_id}")
        return result

    if need == "suspended":
        suspender_id = (
            result.context.get("skill_fixture_instruction_suspender")
            or _ficc_instruction_suspender(seed)
        )
        if not suspender_id:
            result.logs.append(
                "error: no FICC Managing Director INSTRUCTION_APPROVER for suspend"
            )
            result.failed += 1
            result.ok = False
            return result
        suspend_session = _session_for_user(auth, seed, settings, suspender_id)
        result.logs.append(f"suspend instruction {instruction_id} as {suspender_id}")
        response = instruction_service.suspend_instruction(
            suspend_session, instruction_id
        )
        if response.status_code not in range(200, 300):
            result.failed += 1
            result.ok = False
            result.logs.append(f"  -> suspend HTTP {response.status_code} FAIL")
            result.logs.append(f"     {response.text.strip()[:300]}")
            return result
        result.context["suspended_instruction_id"] = instruction_id
        result.succeeded += 1
        result.ok = True
        result.logs.append(f"Skill fixture ready (suspended): {instruction_id}")
        return result

    pay_creator_id = _ficc_payment_creator(seed)
    if not pay_creator_id:
        result.logs.append("error: no FICC middle-office payment creator in directory")
        result.failed += 1
        result.ok = False
        return result

    amount = 1_000_000.0
    value_date = (date.today() + timedelta(days=1)).isoformat()
    pay_session = _session_for_user(auth, seed, settings, pay_creator_id)
    ps = payment_client(settings)
    result.context["skill_fixture_payment_creator"] = pay_creator_id

    result.logs.append(
        f"create payment on {instruction_id} as {pay_creator_id} amount={amount:,.0f}"
    )
    response = ps.create_payment(pay_session, instruction_id, amount, value_date)
    if response.status_code != 201:
        result.failed += 1
        result.ok = False
        result.logs.append(f"  -> create payment HTTP {response.status_code} FAIL")
        result.logs.append(f"     {response.text.strip()[:300]}")
        return result
    payment_id = response.json()["payment_id"]
    result.logs.append(f"  -> HTTP 201 {payment_id}")

    if need == "draft":
        result.context["draft_payment_id"] = payment_id
        result.succeeded += 1
        result.ok = True
        result.logs.append(f"Skill fixture ready (draft): {payment_id}")
        return result

    submitter_id = payment_submitter_for_lob(seed, "FICC", rng=random.Random(0))
    result.logs.append(f"submit payment {payment_id} as {submitter_id}")
    submit_session = _session_for_user(auth, seed, settings, submitter_id)
    response = ps.submit_payment(submit_session, payment_id)
    if response.status_code not in range(200, 300):
        result.failed += 1
        result.ok = False
        result.logs.append(f"  -> submit payment HTTP {response.status_code} FAIL")
        result.logs.append(f"     {response.text.strip()[:300]}")
        # Still expose the DRAFT id so teardown can cancel it.
        result.context["draft_payment_id"] = payment_id
        return result

    result.context["submitted_payment_id"] = payment_id
    result.succeeded += 1
    if need == "used_single_use":
        # Submit saga marks SINGLE_USE backing instruction USED.
        result.context["used_instruction_id"] = instruction_id
        result.ok = True
        result.logs.append(
            f"Skill fixture ready (used_single_use): instruction={instruction_id} "
            f"payment={payment_id}"
        )
        return result

    result.ok = True
    result.logs.append(f"Skill fixture ready (submitted): {payment_id}")
    return result


def teardown_skill_fixture(
    settings: Settings,
    admin_session: SessionCredentials,
    *,
    context: dict[str, str] | None = None,
) -> HarnessActionResult:
    """Cancel payments and suspend the instruction created by setup_skill_fixture."""
    context = dict(context or {})
    result = HarnessActionResult(action="teardown_skill_fixture", requested=0)
    if error := _require_pat(settings):
        result.logs.append(f"error: {error}")
        result.ok = False
        return result

    seed, auth, instruction_service = _clients(settings)
    ps = payment_client(settings)

    pay_creator_id = (
        context.get("skill_fixture_payment_creator") or _ficc_payment_creator(seed)
    )
    payment_ids = [
        pid
        for key in ("draft_payment_id", "submitted_payment_id")
        if (pid := context.get(key))
    ]
    # Deduplicate while preserving order (setup creates one payment at a time).
    seen: set[str] = set()
    unique_payments: list[str] = []
    for pid in payment_ids:
        if pid not in seen:
            seen.add(pid)
            unique_payments.append(pid)

    result.requested = len(unique_payments) + (
        1 if context.get("ficc_standing_instruction_id") else 0
    )

    if unique_payments and pay_creator_id:
        pay_session = _session_for_user(auth, seed, settings, pay_creator_id)
        for payment_id in unique_payments:
            result.logs.append(f"cancel payment {payment_id} as {pay_creator_id}")
            response = ps.cancel_payment(pay_session, payment_id)
            if response.status_code in range(200, 300):
                result.succeeded += 1
                result.logs.append(f"  -> cancel HTTP {response.status_code} OK")
            else:
                # Already cancelled / wrong state — treat as cleaned up.
                result.skipped += 1
                result.logs.append(
                    f"  -> cancel HTTP {response.status_code} "
                    f"(ignored for teardown): {response.text.strip()[:200]}"
                )
    elif unique_payments:
        result.failed += len(unique_payments)
        result.logs.append("error: no payment creator available to cancel fixtures")

    instruction_id = context.get("ficc_standing_instruction_id")
    if instruction_id:
        suspender_id = (
            context.get("skill_fixture_instruction_suspender")
            or _ficc_instruction_suspender(seed)
        )
        if not suspender_id:
            result.failed += 1
            result.logs.append(
                "error: no FICC Managing Director INSTRUCTION_APPROVER for suspend"
            )
        else:
            suspend_session = _session_for_user(auth, seed, settings, suspender_id)
            result.logs.append(f"suspend instruction {instruction_id} as {suspender_id}")
            response = instruction_service.suspend_instruction(
                suspend_session, instruction_id
            )
            if response.status_code in range(200, 300):
                result.succeeded += 1
                result.logs.append(f"  -> suspend HTTP {response.status_code} OK")
            else:
                result.skipped += 1
                result.logs.append(
                    f"  -> suspend HTTP {response.status_code} "
                    f"(ignored for teardown): {response.text.strip()[:200]}"
                )

    result.ok = result.failed == 0
    result.logs.append(
        f"Teardown finished: succeeded={result.succeeded} "
        f"skipped={result.skipped} failed={result.failed}"
    )
    return result


def seed_skill_fixtures(
    settings: Settings,
    admin_session: SessionCredentials,
) -> HarnessActionResult:
    """Backward-compatible alias: setup draft + submitted against one instruction.

    Prefer :func:`setup_skill_fixture` + :func:`teardown_skill_fixture` per case.
    """
    # Build instruction + draft, then a separate submitted payment on the same instruction.
    draft = setup_skill_fixture(settings, admin_session, need="draft")
    if not draft.ok:
        draft.action = "seed_skill_fixtures"
        return draft

    instruction_id = draft.context["ficc_standing_instruction_id"]
    seed, auth, _instruction_service = _clients(settings)
    ps = payment_client(settings)
    pay_creator_id = draft.context.get("skill_fixture_payment_creator") or _ficc_payment_creator(
        seed
    )
    if not pay_creator_id:
        draft.ok = False
        draft.failed += 1
        draft.logs.append("error: no FICC payment creator for submitted leg")
        draft.action = "seed_skill_fixtures"
        return draft

    amount = 1_000_000.0
    value_date = (date.today() + timedelta(days=1)).isoformat()
    pay_session = _session_for_user(auth, seed, settings, pay_creator_id)
    draft.logs.append(f"create second payment on {instruction_id} for SUBMITTED fixture")
    response = ps.create_payment(pay_session, instruction_id, amount, value_date)
    if response.status_code != 201:
        draft.ok = False
        draft.failed += 1
        draft.logs.append(f"  -> create payment HTTP {response.status_code} FAIL")
        draft.action = "seed_skill_fixtures"
        return draft
    submitted_id = response.json()["payment_id"]
    submitter_id = payment_submitter_for_lob(seed, "FICC", rng=random.Random(0))
    submit_session = _session_for_user(auth, seed, settings, submitter_id)
    response = ps.submit_payment(submit_session, submitted_id)
    if response.status_code not in range(200, 300):
        draft.ok = False
        draft.failed += 1
        draft.logs.append(f"  -> submit HTTP {response.status_code} FAIL")
        draft.context["draft_payment_id_extra"] = submitted_id
        draft.action = "seed_skill_fixtures"
        return draft

    draft.context["submitted_payment_id"] = submitted_id
    draft.succeeded += 1
    draft.requested = 3
    draft.action = "seed_skill_fixtures"
    draft.logs.append(
        "Skill fixtures ready: "
        f"instruction={instruction_id} draft={draft.context.get('draft_payment_id')} "
        f"submitted={submitted_id}"
    )
    return draft


def suspend_instructions(
    settings: Settings,
    count: int,
    admin_session: SessionCredentials,
) -> HarnessActionResult:
    result = HarnessActionResult(action="suspend_instructions", requested=count)
    if error := _require_pat(settings):
        result.logs.append(f"error: {error}")
        result.ok = False
        return result

    candidates = _fetch_api_instructions(settings, admin_session, status="APPROVED")
    to_process = candidates[:count]

    if not to_process:
        result.logs.append("No APPROVED instructions available to suspend.")
        return result

    instruction_service = instruction_service_client(settings)
    result.logs.append(f"Suspending up to {len(to_process)} instruction(s)")

    for index, instruction in enumerate(to_process, start=1):
        instruction_id = instruction["instruction_id"]
        status = instruction.get("status", "?")
        owning_lob = instruction.get("owning_lob", "?")
        result.logs.append(
            f"[{index}] {instruction_id} lob={owning_lob} status={status}"
        )
        response = instruction_service.suspend_instruction(admin_session, instruction_id)
        if response.status_code in range(200, 300):
            result.succeeded += 1
            result.logs.append(f"  -> suspend HTTP {response.status_code} OK")
        else:
            result.failed += 1
            result.logs.append(f"  -> suspend HTTP {response.status_code} FAIL")
            detail = response.text.strip()
            if detail:
                result.logs.append(f"     {detail[:300]}")

    result.ok = result.failed == 0
    result.logs.append(
        f"Suspended {result.succeeded} instruction(s) with {result.failed} failure(s)."
    )
    return result


def reactivate_instructions(
    settings: Settings,
    count: int,
    admin_session: SessionCredentials,
) -> HarnessActionResult:
    result = HarnessActionResult(action="reactivate_instructions", requested=count)
    if error := _require_pat(settings):
        result.logs.append(f"error: {error}")
        result.ok = False
        return result

    suspended = _fetch_api_instructions(settings, admin_session, status="SUSPENDED")
    to_process = suspended[:count]

    if not to_process:
        result.logs.append("No SUSPENDED instructions available to reactivate.")
        return result

    instruction_service = instruction_service_client(settings)
    result.logs.append(f"Reactivating up to {len(to_process)} instruction(s)")

    for index, instruction in enumerate(to_process, start=1):
        instruction_id = instruction["instruction_id"]
        owning_lob = instruction.get("owning_lob", "?")
        result.logs.append(f"[{index}] {instruction_id} lob={owning_lob} status=SUSPENDED")
        response = instruction_service.reactivate_instruction(admin_session, instruction_id)
        if response.status_code in range(200, 300):
            result.succeeded += 1
            final_status = response.json().get("status", "REACTIVATED")
            result.logs.append(
                f"  -> reactivate HTTP {response.status_code} OK ({final_status})"
            )
        else:
            result.failed += 1
            result.logs.append(f"  -> reactivate HTTP {response.status_code} FAIL")
            detail = response.text.strip()
            if detail:
                result.logs.append(f"     {detail[:300]}")

    result.ok = result.failed == 0
    result.logs.append(
        f"Reactivated {result.succeeded} instruction(s) with {result.failed} failure(s)."
    )
    return result
