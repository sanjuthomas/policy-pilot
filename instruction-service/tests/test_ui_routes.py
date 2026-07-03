from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from inst.admin import get_admin_subject
from inst.models.api import Subject
from inst.repository import InstructionNotFoundError
from inst.storage import VersionedInstruction
from inst.ui_routes import router


def _versioned(sample_instruction) -> VersionedInstruction:
    from datetime import datetime

    return VersionedInstruction(
        instruction=sample_instruction,
        version_number=1,
        valid_in=datetime.utcnow(),
        valid_out=None,
    )


def test_ui_list_and_get_instruction(sample_instruction) -> None:
    app = FastAPI()
    app.include_router(router)
    admin = Subject(user_id="admin", title="Admin", roles=["PLATFORM_ADMIN"])
    app.dependency_overrides[get_admin_subject] = lambda: admin

    record = _versioned(sample_instruction)
    mock_repo = AsyncMock()
    mock_repo.list_current.return_value = [record]
    mock_repo.get_current.return_value = record

    with patch("inst.ui_routes.InstructionRepository", return_value=mock_repo):
        client = TestClient(app)
        list_response = client.get("/api/ui/instructions", params={"owning_lob": "FICC"})
        assert list_response.status_code == 200
        payload = list_response.json()
        assert payload["count"] == 1
        assert payload["instructions"][0]["instruction_id"] == sample_instruction.instruction_id

        get_response = client.get(f"/api/ui/instructions/{sample_instruction.instruction_id}")
        assert get_response.status_code == 200
        assert get_response.json()["instruction"]["instruction_id"] == sample_instruction.instruction_id


def test_ui_get_instruction_not_found() -> None:
    app = FastAPI()
    app.include_router(router)
    admin = Subject(user_id="admin", title="Admin", roles=["PLATFORM_ADMIN"])
    app.dependency_overrides[get_admin_subject] = lambda: admin

    mock_repo = AsyncMock()
    mock_repo.get_current.side_effect = InstructionNotFoundError("missing")

    with patch("inst.ui_routes.InstructionRepository", return_value=mock_repo):
        client = TestClient(app)
        response = client.get("/api/ui/instructions/missing")
        assert response.status_code == 404


def test_ui_static_pages() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert client.get("/ui").status_code == 200
    assert client.get("/ui/instructions/instr-001").status_code == 200
