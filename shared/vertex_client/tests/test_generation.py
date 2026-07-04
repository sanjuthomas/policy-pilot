from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from vertex_client.generation import VertexGenerativeClient


@pytest.fixture
def client() -> VertexGenerativeClient:
    return VertexGenerativeClient(
        project_id="test-project",
        region="us-central1",
        model="gemini-2.5-flash",
    )


async def test_generate_text_returns_model_output(client: VertexGenerativeClient) -> None:
    mock_response = MagicMock()
    mock_response.text = "  generated answer  "

    with patch.object(client, "_get_client") as mock_get_client:
        mock_get_client.return_value.models.generate_content.return_value = mock_response
        text = await client.generate_text(system="sys", user="question")

    assert text == "generated answer"


async def test_generate_text_includes_history(client: VertexGenerativeClient) -> None:
    mock_response = MagicMock()
    mock_response.text = "follow-up answer"

    with patch.object(client, "_get_client") as mock_get_client:
        mock_get_client.return_value.models.generate_content.return_value = mock_response
        await client.generate_text(
            system="sys",
            user="follow up",
            history=[
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "reply"},
            ],
        )

    _, kwargs = mock_get_client.return_value.models.generate_content.call_args
    contents = kwargs["contents"]
    assert len(contents) == 3
    assert contents[0].role == "user"
    assert contents[1].role == "model"
    assert contents[2].role == "user"


async def test_generate_text_raises_on_empty_response(client: VertexGenerativeClient) -> None:
    mock_response = MagicMock()
    mock_response.text = ""

    with patch.object(client, "_get_client") as mock_get_client:
        mock_get_client.return_value.models.generate_content.return_value = mock_response
        with pytest.raises(RuntimeError, match="empty Vertex generate response"):
            await client.generate_text(system="sys", user="question")


async def test_model_property(client: VertexGenerativeClient) -> None:
    assert client.model == "gemini-2.5-flash"


async def test_close_clears_client(client: VertexGenerativeClient) -> None:
    with patch.object(client, "_get_client") as mock_get_client:
        mock_get_client.return_value = MagicMock()
        client._client = mock_get_client.return_value
        await client.close()
    assert client._client is None
