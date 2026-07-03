"""Deserialize Kafka message values from MongoDB Kafka Connect."""

from __future__ import annotations

import json
from typing import Any


def deserialize_kafka_json(value: bytes) -> Any:
    """Parse a Kafka record value as JSON.

    MongoDB Kafka Connect with ``output.format.value=json`` plus
    ``JsonConverter`` double-encodes documents (JSON string inside JSON).
    Accept both a JSON object and a JSON-encoded JSON string.
    """
    parsed = json.loads(value.decode("utf-8"))
    if isinstance(parsed, str):
        parsed = json.loads(parsed)
    return parsed
