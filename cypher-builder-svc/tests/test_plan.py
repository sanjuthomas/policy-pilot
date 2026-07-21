from fastapi.testclient import TestClient

from cbs.main import app

client = TestClient(app)


def test_plan_alert_count_today() -> None:
    response = client.post(
        "/v1/plan",
        json={
            "question": "How many ALERT events happened today?",
            "mode": "events",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matched"] is True
    assert body["strategy"] == "neo4j_direct"
    assert body["intent_id"] == "planned_graph"
    assert body["planned"][0]["label"] == "count"
    assert "SecurityEvent" in body["planned"][0]["cypher"]
    assert body["meta"]["cypher_class"] == "deterministic"
    assert body["meta"]["builder_version"]
    assert "count" in body["meta"]["plan_labels"]


def test_plan_unmatched() -> None:
    response = client.post(
        "/v1/plan",
        json={"question": "zzzz not a graph question at all", "mode": "events"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matched"] is False
    assert body["planned"] == []
    assert body["intent_id"] is None
