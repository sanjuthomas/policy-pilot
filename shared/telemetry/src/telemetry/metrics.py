from __future__ import annotations

from opentelemetry.metrics import Counter, Histogram, Meter

from telemetry.setup import is_telemetry_enabled

_counter_cache: dict[tuple[int, str], Counter] = {}
_histogram_cache: dict[tuple[int, str], Histogram] = {}


def get_meter(name: str, *, version: str = "0.1.0") -> Meter:
    from opentelemetry import metrics

    return metrics.get_meter(name, version=version)


def record_counter(
    meter: Meter,
    name: str,
    *,
    amount: int = 1,
    attributes: dict[str, str] | None = None,
) -> None:
    if not is_telemetry_enabled():
        return
    cache_key = (id(meter), name)
    counter = _counter_cache.get(cache_key)
    if counter is None:
        counter = meter.create_counter(name)
        _counter_cache[cache_key] = counter
    counter.add(amount, attributes=attributes or {})


def record_histogram(
    meter: Meter,
    name: str,
    value: float,
    *,
    unit: str = "ms",
    attributes: dict[str, str] | None = None,
) -> None:
    if not is_telemetry_enabled():
        return
    cache_key = (id(meter), name)
    histogram = _histogram_cache.get(cache_key)
    if histogram is None:
        histogram = meter.create_histogram(name, unit=unit)
        _histogram_cache[cache_key] = histogram
    histogram.record(value, attributes=attributes or {})
