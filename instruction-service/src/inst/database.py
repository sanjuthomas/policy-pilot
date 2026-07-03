from contextlib import asynccontextmanager
from typing import AsyncIterator

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorClientSession,
    AsyncIOMotorDatabase,
)
from pymongo import ReadPreference

from inst.config import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client


def get_database() -> AsyncIOMotorDatabase:
    return get_client()[settings.mongodb_database]


def get_security_events_database() -> AsyncIOMotorDatabase:
    return get_client()[settings.security_events_database]


@asynccontextmanager
async def mongo_transaction() -> AsyncIterator[AsyncIOMotorClientSession]:
    """Multi-document transaction (requires MongoDB replica set)."""
    client = get_client()
    async with await client.start_session() as session:
        async with session.start_transaction(read_preference=ReadPreference.PRIMARY):
            yield session


async def connect() -> None:
    client = get_client()
    await client.admin.command("ping")
    db = get_database()
    collection = db.instructions
    await collection.create_index(
        [("_id", 1), ("out", 1)],
        unique=True,
        name="instruction_id_out_unique",
    )
    await collection.create_index(
        [("out", 1), ("version_number", 1)],
    )
    await collection.create_index("status")
    await collection.create_index("owning_lob")
    await collection.create_index("wire_scope")
    await collection.create_index("in")

    security_events = get_security_events_database()[settings.security_events_collection]
    await security_events.create_index("timestamp")
    await security_events.create_index("severity")
    await security_events.create_index("event.action")
    await security_events.create_index("event.outcome")
    await security_events.create_index("actor.user_id")
    await security_events.create_index("resource.id")


async def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
