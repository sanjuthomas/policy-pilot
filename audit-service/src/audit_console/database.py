from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from telemetry import mongo_event_listeners

from audit_console.config import settings

_client: AsyncIOMotorClient | None = None


async def connect() -> None:
    global _client
    _client = AsyncIOMotorClient(
        settings.mongodb_uri,
        event_listeners=mongo_event_listeners(),
    )
    await _client.admin.command("ping")


async def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def security_events_db() -> AsyncIOMotorDatabase:
    if _client is None:
        raise RuntimeError("MongoDB not connected")
    return _client[settings.security_events_database]


def audit_db() -> AsyncIOMotorDatabase:
    if _client is None:
        raise RuntimeError("MongoDB not connected")
    return _client[settings.audit_database]
