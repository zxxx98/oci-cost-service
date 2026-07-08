from fastapi.testclient import TestClient
from oci.exceptions import ServiceError

from app.main import app, get_billing_service, validate_startup_settings


class FakeBillingService:
    def month_total(self):
        return {
            "month": "2026-07",
            "currency": "USD",
            "total": 1.23,
            "cached": False,
            "lastFetchedAt": "2026-07-08T00:00:00Z",
        }

    def month_by_service(self):
        return {
            "month": "2026-07",
            "currency": "USD",
            "items": [{"service": "Compute", "total": 1.23}],
            "cached": False,
            "lastFetchedAt": "2026-07-08T00:00:00Z",
        }

    def month_by_resource(self):
        return {
            "month": "2026-07",
            "currency": "USD",
            "items": [
                {
                    "resourceId": "ocid1.instance.example",
                    "service": "Compute",
                    "total": 1.23,
                }
            ],
            "cached": False,
            "lastFetchedAt": "2026-07-08T00:00:00Z",
        }

    def month_daily(self):
        return {
            "month": "2026-07",
            "currency": "USD",
            "items": [{"date": "2026-07-01", "total": 1.23}],
            "cached": False,
            "lastFetchedAt": "2026-07-08T00:00:00Z",
        }


def client() -> TestClient:
    app.dependency_overrides[get_billing_service] = lambda: FakeBillingService()
    app.dependency_overrides[validate_startup_settings] = lambda: None
    app.state.settings_override = lambda: type("Settings", (), {"billing_api_key": "secret"})()
    return TestClient(app)


def test_health_is_public() -> None:
    response = client().get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cost_endpoint_requires_api_key() -> None:
    response = client().get("/cost/month")

    assert response.status_code == 401


def test_month_total_endpoint() -> None:
    response = client().get("/cost/month", headers={"X-API-Key": "secret"})

    assert response.status_code == 200
    assert response.json()["total"] == 1.23


def test_by_service_endpoint() -> None:
    response = client().get("/cost/month/by-service", headers={"X-API-Key": "secret"})

    assert response.status_code == 200
    assert response.json()["items"] == [{"service": "Compute", "total": 1.23}]


def test_by_resource_endpoint() -> None:
    response = client().get("/cost/month/by-resource", headers={"X-API-Key": "secret"})

    assert response.status_code == 200
    assert response.json()["items"][0]["resourceId"] == "ocid1.instance.example"


def test_daily_endpoint() -> None:
    response = client().get("/cost/month/daily", headers={"X-API-Key": "secret"})

    assert response.status_code == 200
    assert response.json()["items"] == [{"date": "2026-07-01", "total": 1.23}]


def test_oci_service_error_maps_to_502() -> None:
    class FailingBillingService:
        def month_total(self):
            raise ServiceError(status=403, code="NotAuthorizedOrNotFound", headers={}, message="denied")

    app.dependency_overrides[get_billing_service] = lambda: FailingBillingService()
    app.dependency_overrides[validate_startup_settings] = lambda: None
    app.state.settings_override = lambda: type("Settings", (), {"billing_api_key": "secret"})()

    response = TestClient(app).get("/cost/month", headers={"X-API-Key": "secret"})

    assert response.status_code == 502
    assert response.json() == {"detail": "OCI Usage API error"}


def test_widget_returns_no_content_for_non_target_server() -> None:
    app.dependency_overrides[get_billing_service] = lambda: FakeBillingService()
    app.dependency_overrides[validate_startup_settings] = lambda: None
    app.state.settings_override = lambda: type(
        "Settings",
        (),
        {"billing_api_key": "secret", "nezha_server_id": 1},
    )()

    response = TestClient(app).get("/widget/month?serverId=2")

    assert response.status_code == 204
    assert response.content == b""


def test_widget_returns_month_cost_for_target_server() -> None:
    app.dependency_overrides[get_billing_service] = lambda: FakeBillingService()
    app.dependency_overrides[validate_startup_settings] = lambda: None
    app.state.settings_override = lambda: type(
        "Settings",
        (),
        {"billing_api_key": "secret", "nezha_server_id": 1},
    )()

    response = TestClient(app).get("/widget/month?serverId=1")

    assert response.status_code == 200
    assert response.json()["total"] == 1.23
