from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from chat_application.cypher import records_to_rows
from chat_application.neo4j import Neo4jClient


def _make_record(data: dict) -> object:
    class Record:
        def keys(self):
            return list(data.keys())

        def __getitem__(self, key):
            return data[key]

    return Record()


class TestRecordsToRowsViaNeo4j:
    def test_converts_driver_records(self) -> None:
        rows = records_to_rows([_make_record({"event_id": "evt-1", "instruction_id": "inst-1"})])
        assert rows == [{"event_id": "evt-1", "instruction_id": "inst-1"}]


class TestNeo4jClient:
    @pytest.mark.asyncio
    async def test_lookup_instruction_for_event(self) -> None:
        client = Neo4jClient()
        mock_record = _make_record({"event_id": "evt-1", "instruction_id": "inst-1"})
        mock_result = MagicMock()
        mock_result.__aiter__ = lambda self: self
        mock_result.__anext__ = AsyncMock(side_effect=[mock_record, StopAsyncIteration])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session = MagicMock(return_value=mock_session)
        client._driver = mock_driver

        rows = await client.lookup_instruction_for_event("evt-1")
        assert rows == [{"event_id": "evt-1", "instruction_id": "inst-1"}]

    @pytest.mark.asyncio
    async def test_run_cypher_validates_and_returns_rows(self) -> None:
        client = Neo4jClient()
        mock_record = _make_record({"total": 3})
        mock_result = MagicMock()
        mock_result.__aiter__ = lambda self: self
        mock_result.__anext__ = AsyncMock(side_effect=[mock_record, StopAsyncIteration])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session = MagicMock(return_value=mock_session)
        client._driver = mock_driver

        rows = await client.run_cypher("MATCH (e) RETURN count(e) AS total LIMIT 1")
        assert rows == [{"total": 3}]

    @pytest.mark.asyncio
    async def test_run_cypher_raises_when_not_connected(self) -> None:
        client = Neo4jClient()
        with pytest.raises(RuntimeError, match="not connected"):
            await client.run_cypher("MATCH (n) RETURN n LIMIT 1")

    @pytest.mark.asyncio
    async def test_close_clears_driver(self) -> None:
        client = Neo4jClient()
        mock_driver = MagicMock()
        mock_driver.close = AsyncMock()
        client._driver = mock_driver

        await client.close()
        assert client._driver is None
