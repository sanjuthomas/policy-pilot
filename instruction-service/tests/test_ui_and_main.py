import sys
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def test_main_health_endpoint() -> None:
    telemetry = MagicMock()
    telemetry.configure_telemetry = lambda *args, **kwargs: None
    telemetry.instrument_app = lambda app: app
    telemetry.get_logger = lambda name: __import__("logging").getLogger(name)
    telemetry.shutdown_telemetry = lambda: None

    with patch.dict(sys.modules, {"telemetry": telemetry}):
        import importlib

        import inst.main as main

        importlib.reload(main)
        with patch.object(main, "connect", AsyncMock()), \
             patch.object(main, "close", AsyncMock()), \
             patch.object(main.service_identity, "login", AsyncMock()):

            with TestClient(main.app) as client:
                response = client.get("/health")
                assert response.status_code == 200
                assert response.json()["status"] == "UP"
