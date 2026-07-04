from __future__ import annotations

import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from telemetry.metrics import get_meter, record_histogram
from telemetry.redaction import redact_headers, redact_json_body
from telemetry.setup import is_telemetry_enabled

logger = logging.getLogger(__name__)


def _split_excluded(excluded_urls: str) -> set[str]:
    return {part.strip() for part in excluded_urls.split(",") if part.strip()}


class HttpPayloadLoggingMiddleware(BaseHTTPMiddleware):
    """Log redacted HTTP request/response bodies and record server duration metrics."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        excluded_urls: str = "/health,/metrics",
        max_body_bytes: int = 8192,
    ) -> None:
        super().__init__(app)
        self._excluded = _split_excluded(excluded_urls)
        self._max_body_bytes = max_body_bytes
        self._meter = get_meter("telemetry.http", version="0.1.0")

    def _is_excluded(self, path: str) -> bool:
        return path in self._excluded

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if self._is_excluded(request.url.path):
            return await call_next(request)

        body = await request.body()
        if is_telemetry_enabled() and body:
            logger.info(
                "http_request method=%s path=%s headers=%s body=%s",
                request.method,
                request.url.path,
                redact_headers(dict(request.headers)),
                redact_json_body(body[: self._max_body_bytes]),
            )

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0

        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk

        if is_telemetry_enabled():
            content_type = response.headers.get("content-type", "")
            if response_body and "json" in content_type.lower():
                logger.info(
                    "http_response method=%s path=%s status=%s duration_ms=%.1f body=%s",
                    request.method,
                    request.url.path,
                    response.status_code,
                    duration_ms,
                    redact_json_body(response_body[: self._max_body_bytes]),
                )
            else:
                logger.info(
                    "http_response method=%s path=%s status=%s duration_ms=%.1f body_bytes=%s",
                    request.method,
                    request.url.path,
                    response.status_code,
                    duration_ms,
                    len(response_body),
                )

            record_histogram(
                self._meter,
                "http.server.request.duration",
                duration_ms,
                unit="ms",
                attributes={
                    "http.request.method": request.method,
                    "http.response.status_code": str(response.status_code),
                    "url.path": request.url.path,
                },
            )

        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )


def add_http_payload_logging(
    app: ASGIApp,
    *,
    excluded_urls: str = "/health,/metrics",
    max_body_bytes: int = 8192,
) -> None:
    app.add_middleware(
        HttpPayloadLoggingMiddleware,
        excluded_urls=excluded_urls,
        max_body_bytes=max_body_bytes,
    )
