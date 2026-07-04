import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorClientSession,
    AsyncIOMotorDatabase,
)
from pymongo import ReadPreference
from pymongo.errors import OperationFailure

from ps.config import settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None

# Pre–composite-_id schema; documents store payment_id only in _id ({id}|{version}).
_LEGACY_PAYMENT_INDEXES = (
    "payment_id_1",
    "payment_id_version_unique",
)


async def connect() -> None:
    global _client
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    await _client.admin.command("ping")
    collection = get_db()[settings.mongodb_collection]
    for index_name in _LEGACY_PAYMENT_INDEXES:
        try:
            await collection.drop_index(index_name)
        except OperationFailure as exc:
            if exc.code != 27:  # IndexNotFound
                raise
    await collection.create_index(
        [("_id", 1), ("out", 1)],
        unique=True,
        name="payment_id_out_unique",
    )
    await collection.create_index([("out", 1), ("version_number", 1)])
    await collection.create_index("status")
    await collection.create_index("owning_lob")
    await collection.create_index("instruction_id")
    await collection.create_index("in")

    security_events = get_security_events_db()[settings.security_events_collection]
    await security_events.create_index("timestamp")
    await security_events.create_index("severity")
    await security_events.create_index("event.action")
    await security_events.create_index("event.outcome")
    await security_events.create_index("actor.user_id")
    await security_events.create_index("resource.id")
    logger.info(
        "MongoDB connected uri=%s db=%s",
        settings.mongodb_uri,
        settings.mongodb_database,
    )


async def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def get_db() -> AsyncIOMotorDatabase:
    if _client is None:
        raise RuntimeError("MongoDB not connected")
    return _client[settings.mongodb_database]


def get_security_events_db() -> AsyncIOMotorDatabase:
    if _client is None:
        raise RuntimeError("MongoDB not connected")
    return _client[settings.security_events_database]


@asynccontextmanager
async def mongo_transaction() -> AsyncIterator[AsyncIOMotorClientSession]:
    """Multi-document transaction (requires MongoDB replica set)."""
    if _client is None:
        raise RuntimeError("MongoDB not connected")
    async with await _client.start_session() as session:
        async with session.start_transaction(read_preference=ReadPreference.PRIMARY):
            yield session
