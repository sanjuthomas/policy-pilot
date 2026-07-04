"""Tests for FastAPI lifespan startup and shutdown."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_consumers() -> None:
    from etl.main import lifespan

    app = FastAPI()

    with (
        patch("etl.main.configure_telemetry"),
        patch("etl.main.instrument_app"),
        patch("etl.main.shutdown_telemetry") as mock_shutdown,
        patch("etl.main.neo4j_writer") as mock_neo4j,
        patch("etl.main.embedding_client") as mock_embedding,
        patch("etl.main.multimodal_store") as mock_multimodal,
        patch("etl.main.instruction_security_event_consumer") as mock_ise,
        patch("etl.main.instruction_consumer") as mock_ic,
        patch("etl.main.payment_security_event_consumer") as mock_pse,
        patch("etl.main.payment_fact_consumer") as mock_pfc,
    ):
        mock_neo4j.connect = AsyncMock()
        mock_neo4j.close = AsyncMock()
        mock_embedding.warmup = AsyncMock()
        mock_embedding.close = AsyncMock()
        mock_embedding.dimension = 768
        mock_multimodal.ensure_indexes = AsyncMock()
        for consumer in (mock_ise, mock_ic, mock_pse, mock_pfc):
            consumer.start = AsyncMock()
            consumer.close = AsyncMock()

        @asynccontextmanager
        async def run_lifespan():
            async with lifespan(app):
                yield

        async with run_lifespan():
            mock_neo4j.connect.assert_awaited_once()
            mock_ise.start.assert_awaited_once()
            mock_ic.start.assert_awaited_once()
            mock_pse.start.assert_awaited_once()
            mock_pfc.start.assert_awaited_once()
            mock_embedding.warmup.assert_awaited_once()
            mock_multimodal.ensure_indexes.assert_awaited_once()

        for consumer in (mock_ise, mock_ic, mock_pse, mock_pfc):
            consumer.close.assert_awaited_once()
        mock_neo4j.close.assert_awaited_once()
        mock_embedding.close.assert_awaited_once()
        mock_shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_continues_when_warmup_fails() -> None:
    from etl.main import lifespan

    app = FastAPI()

    with (
        patch("etl.main.configure_telemetry"),
        patch("etl.main.instrument_app"),
        patch("etl.main.shutdown_telemetry"),
        patch("etl.main.neo4j_writer") as mock_neo4j,
        patch("etl.main.embedding_client") as mock_embedding,
        patch("etl.main.multimodal_store") as mock_multimodal,
        patch("etl.main.instruction_security_event_consumer") as mock_ise,
        patch("etl.main.instruction_consumer") as mock_ic,
        patch("etl.main.payment_security_event_consumer") as mock_pse,
        patch("etl.main.payment_fact_consumer") as mock_pfc,
    ):
        mock_neo4j.connect = AsyncMock()
        mock_neo4j.close = AsyncMock()
        mock_embedding.warmup = AsyncMock(side_effect=RuntimeError("vertex down"))
        mock_embedding.close = AsyncMock()
        mock_multimodal.ensure_indexes = AsyncMock()
        for consumer in (mock_ise, mock_ic, mock_pse, mock_pfc):
            consumer.start = AsyncMock()
            consumer.close = AsyncMock()

        async with lifespan(app):
            pass

        mock_multimodal.ensure_indexes.assert_not_awaited()
