import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any


class PaymentBroadcaster:
    """Fan-out hub for payment change stream events to SSE subscribers."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._lock = asyncio.Lock()

    async def publish(self, payment: dict[str, Any]) -> None:
        async with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            await queue.put(payment)

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        async with self._lock:
            self._subscribers.add(queue)
        try:
            while True:
                payment = await queue.get()
                yield payment
        finally:
            async with self._lock:
                self._subscribers.discard(queue)

    @staticmethod
    def sse_payload(payment: dict[str, Any]) -> str:
        return f"data: {json.dumps(payment, separators=(',', ':'), default=str)}\n\n"
