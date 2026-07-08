from datetime import UTC, datetime
from types import SimpleNamespace

from app.oci_usage import UsageGateway


class FakeUsageClient:
    def __init__(self) -> None:
        self.request = None

    def request_summarized_usages(self, request_summarized_usages_details):
        self.request = request_summarized_usages_details
        return SimpleNamespace(data=SimpleNamespace(items=[]))


def test_usage_gateway_builds_cost_request() -> None:
    fake_client = FakeUsageClient()
    gateway = UsageGateway(fake_client, tenant_id="ocid1.tenancy.example")
    started = datetime(2026, 7, 1, tzinfo=UTC)
    ended = datetime(2026, 7, 8, 12, tzinfo=UTC)

    items = gateway.request_costs(
        started=started,
        ended=ended,
        granularity="DAILY",
        group_by=["service"],
    )

    assert items == []
    assert fake_client.request.time_usage_started == started
    assert fake_client.request.time_usage_ended == ended
    assert fake_client.request.tenant_id == "ocid1.tenancy.example"
    assert fake_client.request.granularity == "DAILY"
    assert fake_client.request.query_type == "COST"
    assert fake_client.request.group_by == ["service"]
