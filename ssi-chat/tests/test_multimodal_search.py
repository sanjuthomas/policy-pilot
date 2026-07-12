from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from chat_application.multimodal_search import (
    MultimodalSearchClient,
    _payload_from_node,
    _source_filter_values,
)


class _Result:
    def __init__(self, *, single=None, rows=None) -> None:
        self._single = single
        self._rows = rows or []

    async def single(self):
        return self._single

    def __aiter__(self):
        async def iterate():
            for row in self._rows:
                yield row

        return iterate()


class _Session:
    def __init__(self, results) -> None:
        self.results = iter(results)
        self.run = AsyncMock(side_effect=lambda *args, **kwargs: next(self.results))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _client(*results) -> tuple[MultimodalSearchClient, _Session]:
    session = _Session(results)
    neo4j = MagicMock()
    neo4j._driver.session.return_value = session
    return MultimodalSearchClient(neo4j), session


def test_source_and_payload_helpers() -> None:
    assert _source_filter_values(None) is None
    assert _source_filter_values("security_events") == [
        "instruction_security_event",
        "payment_security_event",
    ]
    assert _source_filter_values("payment") == ["payment_fact"]
    assert _source_filter_values("custom") == ["custom"]
    assert _payload_from_node({}) == {}
    assert _payload_from_node({"payload_json": '{"id": "one"}'}) == {"id": "one"}
    assert _payload_from_node({"payload_json": {"id": "two"}}) == {"id": "two"}
    client, _ = _client()
    assert client._to_hit(
        {"payload_json": '{"source":"instruction_state","instruction_id":"i1"}'},
        1,
        "vector",
    )["merged"] == {"source": "instruction_state", "instruction_id": "i1"}


@pytest.mark.asyncio
async def test_document_count_and_driver_connection() -> None:
    client, _ = _client(_Result(single={"count": 2}), _Result(single={"count": 1}))
    assert await client.document_count() == 2
    assert await client.has_documents() is True

    disconnected = MagicMock()
    disconnected._driver = None
    with pytest.raises(RuntimeError, match="not connected"):
        await MultimodalSearchClient(disconnected).document_count()


@pytest.mark.asyncio
async def test_search_vector_returns_normalized_hits() -> None:
    node = {
        "payload_json": '{"event_id":"event-1","source":"payment_fact","merged":{"amount":3}}',
        "search_text": "payment",
    }
    client, session = _client(
        _Result(single={"count": 1}),
        _Result(rows=[{"node": node, "score": 0.8}]),
    )

    hits = await client.search_vector([0.1], limit=3, source="payment")

    assert hits == [
        {
            "source": "vector",
            "score": 0.8,
            "event_id": "event-1",
            "instruction_id": None,
            "payment_id": None,
            "search_text": "payment",
            "merged": {"amount": 3},
            "security_event": {},
            "payload": {
                "event_id": "event-1",
                "source": "payment_fact",
                "merged": {"amount": 3},
            },
        }
    ]
    assert session.run.call_args_list[1].kwargs["sources"] == ["payment_fact"]


@pytest.mark.asyncio
async def test_search_vector_short_circuits_without_documents() -> None:
    client, session = _client(_Result(single={"count": 0}))
    assert await client.search_vector([0.1], limit=3) == []
    assert session.run.call_count == 1


@pytest.mark.asyncio
async def test_fetches_exact_documents_and_approval_events() -> None:
    instruction_node = {"payload_json": '{"instruction":{"id":"i1"}}'}
    payment_node = {"payload_json": '{"payment_id":"p1"}'}
    event_node = {"payload_json": '{"event_id":"e1","security_event":{"action":"APPROVE"}}'}
    client, _ = _client(
        _Result(single={"d": instruction_node}),
        _Result(single={"d": payment_node}),
        _Result(single={"d": instruction_node}),
        _Result(rows=[{"d": event_node}]),
        _Result(rows=[{"d": event_node}]),
    )

    instruction = await client.fetch_by_instruction_id("i1")
    payment = await client.fetch_by_payment_id("p1")
    event = await client.fetch_by_event_id("event-1")
    instruction_events = await client.fetch_instruction_approve_events("i1")
    payment_events = await client.fetch_payment_approve_events("p1")

    assert instruction["source"] == "exact_instruction"
    assert instruction["merged"] == {"instruction": {"id": "i1"}}
    assert payment["source"] == "exact_payment"
    assert payment["merged"] == {"payment_id": "p1"}
    assert event["instruction"] == {"id": "i1"}
    assert instruction_events[0]["source"] == "exact_approve_event"
    assert payment_events[0]["source"] == "exact_approve_payment_event"


@pytest.mark.asyncio
async def test_fetch_returns_none_when_document_does_not_exist() -> None:
    client, _ = _client(_Result(single=None))
    assert await client.fetch_by_event_id("missing") is None
