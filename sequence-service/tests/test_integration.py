from __future__ import annotations

import os
import uuid
from datetime import date

import httpx
import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from seq.config import Settings
from seq.models import EntityType, NextSequenceRequest
from seq.repository import SequenceRepository
from seq.service import SequenceService


def _integration_enabled() -> bool:
    return os.environ.get("RUN_SEQUENCE_INTEGRATION") == "1"


def _integration_settings() -> Settings:
    default_uri = "mongodb://localhost:27017/?directConnection=true"
    return Settings(
        mongodb_uri=os.environ.get("SEQUENCE_MONGODB_URI", default_uri),
        mongodb_database=os.environ.get("SEQUENCE_TEST_DATABASE", "ssi_sequences_test"),
        mongodb_collection=os.environ.get("SEQUENCE_TEST_COLLECTION", "sequence_counters"),
    )


@pytest.fixture
async def integration_repo():
    if not _integration_enabled():
        pytest.skip("set RUN_SEQUENCE_INTEGRATION=1 to run live MongoDB integration tests")

    settings = _integration_settings()
    client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
    db = client[settings.mongodb_database]
    collection = db[settings.mongodb_collection]

    suffix = uuid.uuid4().hex[:8]
    test_keys: list[str] = []

    async def allocate(counter_key: str) -> int:
        test_keys.append(counter_key)
        with pytest.MonkeyPatch.context() as patcher:
            patcher.setattr("seq.config.settings", settings)
            patcher.setattr("seq.database._client", client, raising=False)
            repo = SequenceRepository()
            return await repo.allocate_next(counter_key)

    yield settings, collection, allocate, test_keys

    if test_keys:
        await collection.delete_many({"_id": {"$in": test_keys}})
    client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_first_allocation_starts_at_one(integration_repo) -> None:
    _settings, _collection, allocate, _keys = integration_repo
    counter_key = f"20990101-TEST-I-{uuid.uuid4().hex[:6]}"
    seq = await allocate(counter_key)
    assert seq == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_same_counter_key_increments(integration_repo) -> None:
    _settings, _collection, allocate, _keys = integration_repo
    counter_key = f"20990102-TEST-I-{uuid.uuid4().hex[:6]}"
    assert await allocate(counter_key) == 1
    assert await allocate(counter_key) == 2
    assert await allocate(counter_key) == 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_instruction_and_payment_counters_are_independent(integration_repo) -> None:
    settings, _collection, allocate, _keys = integration_repo
    token = uuid.uuid4().hex[:6]
    instruction_key = f"20990103-FICC-I-{token}"
    payment_key = f"20990103-FICC-P-{token}"

    assert await allocate(instruction_key) == 1
    assert await allocate(payment_key) == 1
    assert await allocate(instruction_key) == 2
    assert await allocate(payment_key) == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_different_lobs_have_independent_counters(integration_repo) -> None:
    _settings, _collection, allocate, _keys = integration_repo
    token = uuid.uuid4().hex[:6]
    ficc_key = f"20990104-FICC-I-{token}"
    fx_key = f"20990104-FX-I-{token}"

    assert await allocate(ficc_key) == 1
    assert await allocate(fx_key) == 1
    assert await allocate(ficc_key) == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_allocations_are_unique_and_monotonic(integration_repo) -> None:
    import asyncio

    settings, _collection, _allocate, _keys = integration_repo
    counter_key = f"20990105-TEST-I-{uuid.uuid4().hex[:6]}"
    _keys.append(counter_key)

    client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)

    async def allocate_once() -> int:
        with pytest.MonkeyPatch.context() as patcher:
            patcher.setattr("seq.config.settings", settings)
            patcher.setattr("seq.database._client", client, raising=False)
            repo = SequenceRepository()
            return await repo.allocate_next(counter_key)

    results = await asyncio.gather(*(allocate_once() for _ in range(20)))
    client.close()

    assert sorted(results) == list(range(1, 21))
    assert len(set(results)) == 20


@pytest.mark.integration
@pytest.mark.asyncio
async def test_service_end_to_end_against_mongo(integration_repo) -> None:
    settings, _collection, _allocate, _keys = integration_repo
    client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)

    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr("seq.config.settings", settings)
        patcher.setattr("seq.database._client", client, raising=False)
        service = SequenceService(SequenceRepository())

        response = await service.next_sequence(
            NextSequenceRequest(
                business_date=date(2099, 1, 6),
                owning_lob=f"LOB{uuid.uuid4().hex[:4].upper()}",
                entity_type=EntityType.INSTRUCTION,
            )
        )

    client.close()
    _keys.append(response.counter_key)

    assert response.sequence_number == 1
    assert response.sequence_id.endswith("-I-1")


@pytest.mark.integration
def test_http_api_against_running_service() -> None:
    if not _integration_enabled():
        pytest.skip("set RUN_SEQUENCE_INTEGRATION=1 to run live MongoDB integration tests")

    base_url = os.environ.get("SEQUENCE_SERVICE_URL", "http://localhost:8095").rstrip("/")
    lob = f"HTTP{uuid.uuid4().hex[:4].upper()}"

    with httpx.Client(timeout=10.0) as client:
        health = client.get(f"{base_url}/health")
        if health.status_code != 200:
            pytest.skip(f"sequence-service not reachable at {base_url}")

        first = client.post(
            f"{base_url}/api/v1/sequences/next",
            json={
                "business_date": "2099-01-07",
                "owning_lob": lob,
                "entity_type": "INSTRUCTION",
            },
        )
        second = client.post(
            f"{base_url}/api/v1/sequences/next",
            json={
                "business_date": "2099-01-07",
                "owning_lob": lob,
                "entity_type": "INSTRUCTION",
            },
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["sequence_id"].endswith("-I-1")
    assert second.json()["sequence_id"].endswith("-I-2")
