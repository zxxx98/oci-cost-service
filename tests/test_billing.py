from datetime import UTC, datetime
from types import SimpleNamespace

from app.billing import BillingService
from app.cache import TTLCache


class FakeGateway:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def request_costs(self, *, started, ended, granularity, group_by=None):
        self.calls.append(
            {
                "started": started,
                "ended": ended,
                "granularity": granularity,
                "group_by": group_by,
            }
        )
        return self.items


def usage_item(computed_amount, currency="USD", **kwargs):
    return SimpleNamespace(computed_amount=computed_amount, currency=currency, **kwargs)


def test_month_total_response() -> None:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
    service = BillingService(
        gateway=FakeGateway([usage_item(1.25), usage_item(2.75)]),
        cache=TTLCache(ttl_seconds=60),
    )

    response = service.month_total(now=now)

    assert response["month"] == "2026-07"
    assert response["currency"] == "USD"
    assert response["total"] == 4.0
    assert response["timeUsageStarted"] == "2026-07-01T00:00:00Z"
    assert response["timeUsageEnded"] == "2026-07-08T00:00:00Z"
    assert response["cached"] is False
    assert response["lastFetchedAt"] == "2026-07-08T12:00:00Z"


def test_month_by_service_response() -> None:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
    service = BillingService(
        gateway=FakeGateway(
            [
                usage_item(1.5, service="Compute"),
                usage_item(2.5, service="Block Storage"),
            ]
        ),
        cache=TTLCache(ttl_seconds=60),
    )

    response = service.month_by_service(now=now)

    assert response["items"] == [
        {"service": "Block Storage", "total": 2.5},
        {"service": "Compute", "total": 1.5},
    ]


def test_month_by_resource_response() -> None:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
    service = BillingService(
        gateway=FakeGateway(
            [
                usage_item(3.0, resource_id="ocid1.instance.example", service="Compute"),
            ]
        ),
        cache=TTLCache(ttl_seconds=60),
    )

    response = service.month_by_resource(now=now)

    assert response["items"] == [
        {
            "resourceId": "ocid1.instance.example",
            "service": "Compute",
            "total": 3.0,
        }
    ]


def test_month_daily_response() -> None:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
    service = BillingService(
        gateway=FakeGateway(
            [
                usage_item(1.0, time_usage_started=datetime(2026, 7, 1, tzinfo=UTC)),
                usage_item(2.0, time_usage_started=datetime(2026, 7, 2, tzinfo=UTC)),
            ]
        ),
        cache=TTLCache(ttl_seconds=60),
    )

    response = service.month_daily(now=now)

    assert response["items"] == [
        {"date": "2026-07-01", "total": 1.0},
        {"date": "2026-07-02", "total": 2.0},
    ]


def test_cache_hit_marks_response_cached() -> None:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
    gateway = FakeGateway([usage_item(1.0)])
    service = BillingService(gateway=gateway, cache=TTLCache(ttl_seconds=60))

    first = service.month_total(now=now)
    second = service.month_total(now=now)

    assert first["cached"] is False
    assert second["cached"] is True
    assert len(gateway.calls) == 1
