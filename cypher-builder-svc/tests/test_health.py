from fastapi.testclient import TestClient

from cbs.main import app

client = TestClient(app)


def test_health_up() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "UP"}
