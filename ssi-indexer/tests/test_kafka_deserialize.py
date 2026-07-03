from __future__ import annotations

import json

from etl.kafka_deserialize import deserialize_kafka_json


def test_deserialize_kafka_json_object() -> None:
    payload = {"_id": "instr-1|1", "status": "DRAFT"}
    value = json.dumps(payload).encode("utf-8")
    assert deserialize_kafka_json(value) == payload


def test_deserialize_kafka_json_double_encoded_string() -> None:
    payload = {"_id": "se-001", "severity": "INFO"}
    value = json.dumps(json.dumps(payload)).encode("utf-8")
    assert deserialize_kafka_json(value) == payload
