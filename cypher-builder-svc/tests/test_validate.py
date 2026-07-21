from fastapi.testclient import TestClient

from cbs.main import app

client = TestClient(app)

READ_CYPHER = """
MATCH (e:SecurityEvent {severity: 'ALERT'})
WHERE date(datetime(e.timestamp)) = date()
RETURN count(e) AS total
LIMIT 1
"""


def test_validate_ok() -> None:
    response = client.post("/v1/validate", json={"cypher": READ_CYPHER})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["cypher"]
    assert body["error"] is None


def test_validate_rejects_write() -> None:
    response = client.post(
        "/v1/validate",
        json={"cypher": "MATCH (n) DELETE n"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["cypher"] is None
    assert body["error"]
