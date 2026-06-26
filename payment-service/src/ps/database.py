import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from ps.config import settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None


async def connect() -> None:
    global _client
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    logger.info("MongoDB connected uri=%s db=%s", settings.mongodb_uri, settings.mongodb_database)


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
