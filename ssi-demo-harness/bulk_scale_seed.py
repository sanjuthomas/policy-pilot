#!/usr/bin/env python3
"""Large-scale demo seed: instructions, payments, and backdated timestamps."""

from __future__ import annotations

import argparse
import json
import random
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import httpx
from harness.config import Settings
from harness.fixtures import build_instruction_payload, load_users, user_by_id
from harness.helpers import (
    _approver_for_instruction,
    _approver_for_payment,
    _fetch_approved_instructions,
    _instruction_submitter,
    _rejector_for_payment,
    _session_for_user,
    _valid_instruction_seed_pairs,
    auth_client,
    build_payment_seed_plan,
    instruction_service_client,
    payment_client,
    payment_submitter_for_lob,
)
from harness.zitadel_auth import SessionCredentials, ZitadelAuthClient
from pymongo import MongoClient

INSTRUCTION_COUNT = 1000
SINGLE_USE_COUNT = 100  # 10%
APPROVE_INSTRUCTION_COUNT = 900  # 90%
DRAFT_ONLY_INSTRUCTION_COUNT = 50
SUBMITTED_ONLY_INSTRUCTION_COUNT = 50

PAYMENT_COUNT = 2000
APPROVE_PAYMENT_COUNT = 1800  # 90%
REJECT_PAYMENT_COUNT = 100  # 5%
DRAFT_ONLY_PAYMENT_COUNT = 50
SUBMITTED_ONLY_PAYMENT_COUNT = 50

DAYS_BACK = 365
RNG = random.Random(42)
PAYMENT_WORKERS = 12


class PaymentFate(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    DRAFT = "draft"
    SUBMITTED = "submitted"


@dataclass
class PlannedInstruction:
    instruction_id: str
    owning_lob: str
    creator_id: str
    creator_title: str
    creator_supervisor_id: str | None
    created_at: datetime
    approve: bool
    submit: bool


@dataclass
class PlannedPayment:
    payment_id: str
    owning_lob: str
    created_at: datetime
    value_date: str
    fate: PaymentFate


@dataclass
class PaymentJob:
    index: int
    creator_id: str
    amount: float
    fate: PaymentFate
    instruction: PlannedInstruction
    created_at: datetime
    value_date: str


class SessionCache:
    def __init__(self, auth: ZitadelAuthClient, seed, settings: Settings) -> None:
        self._auth = auth
        self._seed = seed
        self._settings = settings
        self._sessions: dict[str, SessionCredentials] = {}
        self._lock = threading.Lock()

    def get(self, user_id: str) -> SessionCredentials:
        with self._lock:
            cached = self._sessions.get(user_id)
            if cached is not None:
                return cached
            session = _session_for_user(self._auth, self._seed, self._settings, user_id)
            self._sessions[user_id] = session
            return session

    def warm(self, user_ids: set[str]) -> None:
        _log(f"Warming {len(user_ids)} user sessions…")
        with ThreadPoolExecutor(max_workers=min(16, len(user_ids) or 1)) as pool:
            list(pool.map(self.get, sorted(user_ids)))


class FastPaymentClient:
    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.payment_service_url.rstrip("/")
        self.api_prefix = settings.payment_service_api_prefix.rstrip("/")
        self._local = threading.local()

    def _client(self) -> httpx.Client:
        client = getattr(self._local, "client", None)
        if client is None:
            client = httpx.Client(timeout=60.0)
            self._local.client = client
        return client

    def _url(self, path: str) -> str:
        return f"{self.base_url}{self.api_prefix}{path}"

    def _headers(self, session: SessionCredentials) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {session.session_token}",
            "X-Session-Id": session.session_id,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def create_payment(
        self,
        session: SessionCredentials,
        instruction_id: str,
        amount: float,
        value_date: str,
    ) -> httpx.Response:
        return self._client().post(
            self._url("/payments"),
            headers=self._headers(session),
            json={
                "instruction_id": instruction_id,
                "amount": amount,
                "value_date": value_date,
            },
        )

    def submit_payment(self, session: SessionCredentials, payment_id: str) -> httpx.Response:
        return self._client().post(
            self._url(f"/payments/{payment_id}/submit"),
            headers=self._headers(session),
        )

    def approve_payment(self, session: SessionCredentials, payment_id: str) -> httpx.Response:
        return self._client().post(
            self._url(f"/payments/{payment_id}/approve"),
            headers=self._headers(session),
        )

    def reject_payment(
        self,
        session: SessionCredentials,
        payment_id: str,
        *,
        reason: str,
    ) -> httpx.Response:
        return self._client().post(
            self._url(f"/payments/{payment_id}/reject"),
            headers=self._headers(session),
            json={"reason": reason},
        )


def _log(msg: str) -> None:
    print(msg, flush=True)


def _random_created_at(rng: random.Random) -> datetime:
    days_ago = rng.randint(0, DAYS_BACK)
    hour = rng.randint(8, 18)
    minute = rng.randint(0, 59)
    base = datetime.now(UTC).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return base - timedelta(days=days_ago)


def _deterministic_created_at(entity_id: str) -> datetime:
    rng = random.Random(entity_id)
    return _random_created_at(rng)


def _value_date_on_or_after(created_at: datetime, rng: random.Random) -> str:
    offset = rng.randint(0, 45)
    return (created_at.date() + timedelta(days=offset)).isoformat()


def _admin_session(settings: Settings, seed) -> SessionCredentials:
    auth = auth_client(settings)
    return _session_for_user(auth, seed, settings, "admin-001")


def _build_instruction_plan(settings: Settings, seed) -> list[tuple[str, str, str, str]]:
    pairs = _valid_instruction_seed_pairs(seed)
    types = ["SINGLE_USE"] * SINGLE_USE_COUNT + ["STANDING"] * (
        INSTRUCTION_COUNT - SINGLE_USE_COUNT
    )
    RNG.shuffle(types)
    plan: list[tuple[str, str, str, str]] = []
    for index in range(INSTRUCTION_COUNT):
        creator_id, owning_lob = pairs[index % len(pairs)]
        currency = "USD" if owning_lob != "FX" else "EUR"
        plan.append((creator_id, owning_lob, types[index], currency))
    return plan


def create_instructions(settings: Settings, seed) -> list[PlannedInstruction]:
    auth = auth_client(settings)
    instruction_service = instruction_service_client(settings)
    submitter_id = _instruction_submitter(seed)
    submitter = _session_for_user(auth, seed, settings, submitter_id)

    plan = _build_instruction_plan(settings, seed)
    created: list[PlannedInstruction] = []

    _log(f"Creating {INSTRUCTION_COUNT} instructions…")
    for index, (creator_id, owning_lob, instruction_type, currency) in enumerate(plan, start=1):
        creator = user_by_id(seed, creator_id)
        session = _session_for_user(auth, seed, settings, creator_id)
        payload = build_instruction_payload(
            owning_lob=owning_lob,
            instruction_type=instruction_type,
            currency=currency,
        )
        response = instruction_service.create_instruction(session, payload)
        if response.status_code != 201:
            _log(f"  [{index}] create FAIL HTTP {response.status_code}: {response.text[:200]}")
            continue
        instruction_id = response.json()["instruction_id"]
        slot = index - 1
        if slot < DRAFT_ONLY_INSTRUCTION_COUNT:
            submit, approve = False, False
        elif slot < DRAFT_ONLY_INSTRUCTION_COUNT + SUBMITTED_ONLY_INSTRUCTION_COUNT:
            submit, approve = True, False
        else:
            submit, approve = True, True

        planned = PlannedInstruction(
            instruction_id=instruction_id,
            owning_lob=owning_lob,
            creator_id=creator_id,
            creator_title=creator.title,
            creator_supervisor_id=creator.supervisor_id,
            created_at=_random_created_at(RNG),
            approve=approve,
            submit=submit,
        )
        created.append(planned)

        if planned.submit:
            submit_resp = instruction_service.submit_instruction(submitter, instruction_id)
            if submit_resp.status_code not in range(200, 300):
                _log(f"  [{index}] submit FAIL {instruction_id}: HTTP {submit_resp.status_code}")

        if planned.approve:
            approver_id = _approver_for_instruction(
                seed,
                owning_lob,
                creator_id,
                creator.title,
                creator.supervisor_id,
                rng=RNG,
            )
            if not approver_id:
                _log(f"  [{index}] no approver for {instruction_id}")
            else:
                approver = _session_for_user(auth, seed, settings, approver_id)
                appr_resp = instruction_service.approve_instruction(approver, instruction_id)
                if appr_resp.status_code not in range(200, 300):
                    _log(f"  [{index}] approve FAIL {instruction_id}: HTTP {appr_resp.status_code}")

        if index % 100 == 0:
            _log(f"  … {index}/{INSTRUCTION_COUNT} instructions processed")

    approved = sum(1 for item in created if item.approve)
    _log(f"Instructions created: {len(created)} (planned approve={approved})")
    return created


def _load_instructions_from_store(settings: Settings, seed) -> list[PlannedInstruction]:
    client = MongoClient(settings.mongodb_uri)
    inst_col = client["ssi_cash_instructions"]["instructions"]
    latest: dict[str, dict] = {}
    for doc in inst_col.find({}, sort=[("in", 1)]):
        entity_id = str(doc["_id"]).split("|", 1)[0]
        latest[entity_id] = doc
    client.close()

    planned: list[PlannedInstruction] = []
    for instruction_id, doc in sorted(latest.items()):
        payload = doc.get("payload") or {}
        status = doc.get("status") or payload.get("status") or "DRAFT"
        planned.append(
            PlannedInstruction(
                instruction_id=instruction_id,
                owning_lob=doc.get("owning_lob") or payload.get("owning_lob") or "FICC",
                creator_id="mo-100",
                creator_title="Analyst",
                creator_supervisor_id=None,
                created_at=_deterministic_created_at(instruction_id),
                approve=status in {"APPROVED", "USED"},
                submit=status in {"SUBMITTED", "APPROVED", "USED", "REJECTED"},
            )
        )
    _log(f"Loaded {len(planned)} instructions from MongoDB")
    return planned


def _payment_status_counts(settings: Settings) -> Counter[str]:
    client = MongoClient(settings.mongodb_uri)
    pay_col = client["ssi_cash_activities"]["payments"]
    latest: dict[str, str] = {}
    for doc in pay_col.find({}, sort=[("in", 1)]):
        entity_id = str(doc["_id"]).split("|", 1)[0]
        payload = doc.get("payload") or {}
        latest[entity_id] = doc.get("status") or payload.get("status") or "DRAFT"
    client.close()
    return Counter(latest.values())


def _payment_fates(remaining: int, existing: Counter[str]) -> list[PaymentFate]:
    targets = {
        PaymentFate.APPROVE: APPROVE_PAYMENT_COUNT,
        PaymentFate.REJECT: REJECT_PAYMENT_COUNT,
        PaymentFate.DRAFT: DRAFT_ONLY_PAYMENT_COUNT,
        PaymentFate.SUBMITTED: SUBMITTED_ONLY_PAYMENT_COUNT,
    }
    status_map = {
        "APPROVED": PaymentFate.APPROVE,
        "REJECTED": PaymentFate.REJECT,
        "DRAFT": PaymentFate.DRAFT,
        "SUBMITTED": PaymentFate.SUBMITTED,
    }
    have = Counter({PaymentFate.APPROVE: 0, PaymentFate.REJECT: 0, PaymentFate.DRAFT: 0, PaymentFate.SUBMITTED: 0})
    for status, count in existing.items():
        fate = status_map.get(status)
        if fate is not None:
            have[fate] += count

    fates: list[PaymentFate] = []
    for fate, target in targets.items():
        need = max(0, target - have[fate])
        fates.extend([fate] * need)
    if len(fates) > remaining:
        fates = fates[:remaining]
    while len(fates) < remaining:
        fates.append(PaymentFate.APPROVE)
    RNG.shuffle(fates)
    return fates


def _resolve_standing(instructions: list[PlannedInstruction], settings: Settings, seed) -> list[PlannedInstruction]:
    approved = [item for item in instructions if item.approve]
    if approved:
        client = MongoClient(settings.mongodb_uri)
        inst_col = client["ssi_cash_instructions"]["instructions"]
        usable: list[PlannedInstruction] = []
        for item in approved:
            doc = inst_col.find_one(
                {"_id": {"$regex": f"^{item.instruction_id}\\|"}},
                sort=[("in", -1)],
            )
            if not doc:
                continue
            payload = doc.get("payload") or {}
            status = doc.get("status") or payload.get("status") or "DRAFT"
            if status == "APPROVED":
                usable.append(item)
        client.close()
        if usable:
            return usable
    admin = _admin_session(settings, seed)
    approved_pool = _fetch_approved_instructions(settings, admin)
    return [
        PlannedInstruction(
            instruction_id=item["instruction_id"],
            owning_lob=item["owning_lob"],
            creator_id=(item.get("created_by") or {}).get("user_id", "pay-101"),
            creator_title=(item.get("created_by") or {}).get("title", "Analyst"),
            creator_supervisor_id=(item.get("created_by") or {}).get("supervisor_id"),
            created_at=_random_created_at(RNG),
            approve=True,
            submit=True,
        )
        for item in approved_pool
    ]


def _execute_payment_job(
    job: PaymentJob,
    *,
    seed,
    settings: Settings,
    sessions: SessionCache,
    ps: FastPaymentClient,
) -> PlannedPayment | None:
    try:
        creator = user_by_id(seed, job.creator_id)
        session = sessions.get(job.creator_id)
        response = ps.create_payment(
            session,
            job.instruction.instruction_id,
            job.amount,
            job.value_date,
        )
        if response.status_code != 201:
            _log(
                f"  [{job.index}] create payment FAIL: HTTP {response.status_code} "
                f"{response.text[:120]}"
            )
            return None
        payment_id = response.json()["payment_id"]
        planned = PlannedPayment(
            payment_id=payment_id,
            owning_lob=job.instruction.owning_lob,
            created_at=job.created_at,
            value_date=job.value_date,
            fate=job.fate,
        )

        if job.fate in (PaymentFate.APPROVE, PaymentFate.REJECT, PaymentFate.SUBMITTED):
            submitter_id = payment_submitter_for_lob(seed, job.instruction.owning_lob, rng=RNG)
            submitter = sessions.get(submitter_id)
            sub_resp = ps.submit_payment(submitter, payment_id)
            if sub_resp.status_code not in range(200, 300):
                _log(f"  [{job.index}] submit payment FAIL {payment_id}: HTTP {sub_resp.status_code}")

        if job.fate == PaymentFate.APPROVE:
            pay_detail = {
                "payment_id": payment_id,
                "owning_lob": job.instruction.owning_lob,
                "amount": job.amount,
                "created_by": {
                    "user_id": job.creator_id,
                    "supervisor_id": creator.supervisor_id,
                },
            }
            approver_id = _approver_for_payment(seed, pay_detail, rng=RNG)
            if approver_id:
                approver = sessions.get(approver_id)
                appr = ps.approve_payment(approver, payment_id)
                if appr.status_code not in range(200, 300):
                    _log(f"  [{job.index}] approve payment FAIL {payment_id}: HTTP {appr.status_code}")
            else:
                _log(f"  [{job.index}] no payment approver for {payment_id}")

        if job.fate == PaymentFate.REJECT:
            pay_detail = {
                "payment_id": payment_id,
                "owning_lob": job.instruction.owning_lob,
                "amount": job.amount,
                "created_by": {"user_id": job.creator_id},
            }
            rejector_id = _rejector_for_payment(seed, pay_detail, rng=RNG)
            if rejector_id:
                rejector = sessions.get(rejector_id)
                rej = ps.reject_payment(rejector, payment_id, reason="Bulk seed rejection")
                if rej.status_code not in range(200, 300):
                    _log(f"  [{job.index}] reject payment FAIL {payment_id}: HTTP {rej.status_code}")

        return planned
    except Exception as exc:
        _log(f"  [{job.index}] payment error: {exc}")
        return None


def create_payments(
    settings: Settings,
    seed,
    instructions: list[PlannedInstruction],
    *,
    target_count: int = PAYMENT_COUNT,
    workers: int = PAYMENT_WORKERS,
) -> list[PlannedPayment]:
    existing_counts = _payment_status_counts(settings)
    existing_total = sum(existing_counts.values())
    remaining = max(0, target_count - existing_total)
    if remaining == 0:
        _log(f"Already have {existing_total} payments — skipping creation")
        return _load_existing_payments(settings)

    standing = _resolve_standing(instructions, settings, seed)
    if not standing:
        raise RuntimeError("no approved instructions available for payments")

    amount_plan = build_payment_seed_plan(remaining, seed=seed, rng=RNG)
    fates = _payment_fates(remaining, existing_counts)
    sessions = SessionCache(auth_client(settings), seed, settings)
    ps = FastPaymentClient(settings)

    user_ids: set[str] = set()
    for creator_id, _amount in amount_plan:
        user_ids.add(creator_id)
    for user in seed.users:
        if "PAYMENT_CREATOR" in user.roles or "PAYMENT_APPROVER" in user.roles:
            user_ids.add(user.user_id)
    sessions.warm(user_ids)

    jobs: list[PaymentJob] = []
    for index, ((creator_id, amount), fate) in enumerate(zip(amount_plan, fates, strict=True), start=1):
        creator = user_by_id(seed, creator_id)
        matching = [
            instr
            for instr in standing
            if instr.owning_lob in creator.covering_lobs or not creator.covering_lobs
        ]
        if not matching:
            matching = standing
        instruction = matching[index % len(matching)]
        created_at = _random_created_at(RNG)
        value_date = _value_date_on_or_after(created_at, RNG)
        jobs.append(
            PaymentJob(
                index=existing_total + index,
                creator_id=creator_id,
                amount=amount,
                fate=fate,
                instruction=instruction,
                created_at=created_at,
                value_date=value_date,
            )
        )

    _log(f"Creating {remaining} payments with {workers} workers (existing={existing_total})…")
    created: list[PlannedPayment] = []
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(
                _execute_payment_job,
                job,
                seed=seed,
                settings=settings,
                sessions=sessions,
                ps=ps,
            )
            for job in jobs
        ]
        for future in as_completed(futures):
            planned = future.result()
            if planned is not None:
                created.append(planned)
            done += 1
            if done % 200 == 0:
                _log(f"  … {done}/{remaining} new payments processed")

    all_payments = _load_existing_payments(settings)
    _log(
        f"Payments total: {len(all_payments)} "
        f"(new={len(created)}, approve={sum(1 for p in all_payments if p.fate == PaymentFate.APPROVE)}, "
        f"reject={sum(1 for p in all_payments if p.fate == PaymentFate.REJECT)}, "
        f"draft={sum(1 for p in all_payments if p.fate == PaymentFate.DRAFT)}, "
        f"submitted={sum(1 for p in all_payments if p.fate == PaymentFate.SUBMITTED)})"
    )
    return all_payments


def _load_existing_payments(settings: Settings) -> list[PlannedPayment]:
    client = MongoClient(settings.mongodb_uri)
    pay_col = client["ssi_cash_activities"]["payments"]
    latest: dict[str, dict] = {}
    for doc in pay_col.find({}, sort=[("in", 1)]):
        entity_id = str(doc["_id"]).split("|", 1)[0]
        latest[entity_id] = doc
    client.close()

    status_to_fate = {
        "APPROVED": PaymentFate.APPROVE,
        "REJECTED": PaymentFate.REJECT,
        "DRAFT": PaymentFate.DRAFT,
        "SUBMITTED": PaymentFate.SUBMITTED,
    }
    planned: list[PlannedPayment] = []
    for payment_id, doc in sorted(latest.items()):
        payload = doc.get("payload") or {}
        status = doc.get("status") or payload.get("status") or "DRAFT"
        created_at = _deterministic_created_at(payment_id)
        value_date = _value_date_on_or_after(created_at, random.Random(payment_id))
        planned.append(
            PlannedPayment(
                payment_id=payment_id,
                owning_lob=payload.get("owning_lob") or "FICC",
                created_at=created_at,
                value_date=value_date,
                fate=status_to_fate.get(status, PaymentFate.DRAFT),
            )
        )
    return planned


def _patch_mongo_timestamps(
    settings: Settings,
    instructions: list[PlannedInstruction],
    payments: list[PlannedPayment],
) -> None:
    _log("Patching MongoDB created timestamps…")
    client = MongoClient(settings.mongodb_uri)
    inst_col = client["ssi_cash_instructions"]["instructions"]
    pay_col = client["ssi_cash_activities"]["payments"]

    for item in instructions:
        ts = item.created_at.replace(tzinfo=None)
        ts_str = ts.isoformat() + "Z"
        for doc in inst_col.find({"_id": {"$regex": f"^{item.instruction_id}\\|"}}):
            payload = doc.get("payload", {})
            payload["created_at"] = ts_str
            payload["updated_at"] = ts_str
            inst_col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"in": ts_str, "payload": payload}},
            )

    for item in payments:
        ts = item.created_at.replace(tzinfo=None)
        ts_str = ts.isoformat() + "Z"
        for doc in pay_col.find({"_id": {"$regex": f"^{item.payment_id}\\|"}}):
            payload = doc.get("payload", {})
            payload["created_at"] = ts_str
            payload["updated_at"] = ts_str
            payload["value_date"] = item.value_date
            pay_col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"in": ts_str, "payload": payload}},
            )
    client.close()


def _write_patch_manifest(
    instructions: list[PlannedInstruction],
    payments: list[PlannedPayment],
    path: str = "/tmp/bulk_seed_timestamps.json",
) -> None:
    payload = {
        "instructions": [
            {
                "instruction_id": item.instruction_id,
                "created_at": item.created_at.isoformat(),
            }
            for item in instructions
        ],
        "payments": [
            {
                "payment_id": item.payment_id,
                "created_at": item.created_at.isoformat(),
                "value_date": item.value_date,
            }
            for item in payments
        ],
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    _log(f"Wrote patch manifest to {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bulk seed instructions and payments")
    parser.add_argument("--skip-instructions", action="store_true")
    parser.add_argument("--payments-only", action="store_true")
    parser.add_argument("--payment-count", type=int, default=PAYMENT_COUNT)
    parser.add_argument("--workers", type=int, default=PAYMENT_WORKERS)
    parser.add_argument("--patch-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    started = time.time()
    args = parse_args()
    settings = Settings()
    seed = load_users(settings)
    if not settings.zitadel_service_pat:
        _log("error: ZITADEL service PAT required")
        return 1

    if args.patch_only:
        instructions = _load_instructions_from_store(settings, seed)
        payments = _load_existing_payments(settings)
        _patch_mongo_timestamps(settings, instructions, payments)
        _write_patch_manifest(instructions, payments)
        _log("Patch-only complete")
        return 0

    if args.skip_instructions or args.payments_only:
        instructions = _load_instructions_from_store(settings, seed)
    else:
        instructions = create_instructions(settings, seed)

    payments = create_payments(
        settings,
        seed,
        instructions,
        target_count=args.payment_count,
        workers=args.workers,
    )
    _patch_mongo_timestamps(settings, instructions, payments)
    _write_patch_manifest(instructions, payments)

    elapsed = time.time() - started
    _log(f"Bulk seed complete in {elapsed / 60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
