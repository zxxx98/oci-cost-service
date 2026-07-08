from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Callable

from app.cache import TTLCache
from app.time_utils import current_utc_month_range, iso_z, month_key


class BillingService:
    def __init__(self, gateway: Any, cache: TTLCache[dict[str, Any]]) -> None:
        self._gateway = gateway
        self._cache = cache

    def month_total(self, now: datetime | None = None) -> dict[str, Any]:
        current = now or datetime.now(UTC)
        return self._cached("month_total", current, lambda: self._month_total(current))

    def month_by_service(self, now: datetime | None = None) -> dict[str, Any]:
        current = now or datetime.now(UTC)
        return self._cached(
            "month_by_service",
            current,
            lambda: self._grouped(current, ["service"], "service"),
        )

    def month_by_resource(self, now: datetime | None = None) -> dict[str, Any]:
        current = now or datetime.now(UTC)
        return self._cached("month_by_resource", current, lambda: self._resources(current))

    def month_daily(self, now: datetime | None = None) -> dict[str, Any]:
        current = now or datetime.now(UTC)
        return self._cached("month_daily", current, lambda: self._daily(current))

    def _cached(
        self,
        key: str,
        now: datetime,
        factory: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        cached = self._cache.get(key, now=now)
        if cached is not None:
            result = dict(cached)
            result["cached"] = True
            return result
        result = factory()
        self._cache.set(key, result, now=now)
        return result

    def _base(self, now: datetime) -> dict[str, Any]:
        started, ended = current_utc_month_range(now)
        return {
            "month": month_key(now),
            "currency": "USD",
            "timeUsageStarted": iso_z(started),
            "timeUsageEnded": iso_z(ended),
            "cached": False,
            "lastFetchedAt": iso_z(now),
        }

    def _month_total(self, now: datetime) -> dict[str, Any]:
        started, ended = current_utc_month_range(now)
        items = self._gateway.request_costs(
            started=started,
            ended=ended,
            granularity="MONTHLY",
            group_by=[],
        )
        response = self._base(now)
        response["total"] = round(sum(_amount(item) for item in items), 6)
        response["currency"] = _currency(items)
        return response

    def _grouped(self, now: datetime, group_by: list[str], output_key: str) -> dict[str, Any]:
        started, ended = current_utc_month_range(now)
        items = self._gateway.request_costs(
            started=started,
            ended=ended,
            granularity="MONTHLY",
            group_by=group_by,
        )
        totals: dict[str, float] = defaultdict(float)
        for item in items:
            label = str(getattr(item, output_key, None) or "Unknown")
            totals[label] += _amount(item)
        response = self._base(now)
        response["currency"] = _currency(items)
        response["items"] = [
            {output_key: key, "total": round(value, 6)}
            for key, value in sorted(totals.items(), key=lambda pair: pair[1], reverse=True)
        ]
        return response

    def _resources(self, now: datetime) -> dict[str, Any]:
        started, ended = current_utc_month_range(now)
        items = self._gateway.request_costs(
            started=started,
            ended=ended,
            granularity="MONTHLY",
            group_by=["resourceId", "service"],
        )
        response = self._base(now)
        response["currency"] = _currency(items)
        response["items"] = [
            {
                "resourceId": str(getattr(item, "resource_id", None) or "Unknown"),
                "service": str(getattr(item, "service", None) or "Unknown"),
                "total": round(_amount(item), 6),
            }
            for item in sorted(items, key=_amount, reverse=True)
        ]
        return response

    def _daily(self, now: datetime) -> dict[str, Any]:
        started, ended = current_utc_month_range(now)
        items = self._gateway.request_costs(
            started=started,
            ended=ended,
            granularity="DAILY",
            group_by=[],
        )
        response = self._base(now)
        response["currency"] = _currency(items)
        response["items"] = [
            {
                "date": getattr(item, "time_usage_started").astimezone(UTC).date().isoformat(),
                "total": round(_amount(item), 6),
            }
            for item in sorted(items, key=lambda item: getattr(item, "time_usage_started"))
        ]
        return response


def _amount(item: Any) -> float:
    value = getattr(item, "computed_amount", 0) or 0
    return float(value)


def _currency(items: list[Any]) -> str:
    for item in items:
        value = getattr(item, "currency", None)
        if value:
            return str(value)
    return "USD"
