from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import require_api_key
from app.config import Settings


def build_client() -> TestClient:
    app = FastAPI()

    def settings_override() -> Settings:
        return Settings(BILLING_API_KEY="expected-secret")

    @app.get("/private", dependencies=[Depends(require_api_key)])
    def private_route() -> dict[str, str]:
        return {"ok": "true"}

    app.state.settings_override = settings_override
    return TestClient(app)


def test_rejects_missing_api_key() -> None:
    client = build_client()

    response = client.get("/private")

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_rejects_invalid_api_key() -> None:
    client = build_client()

    response = client.get("/private", headers={"X-API-Key": "wrong"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_accepts_valid_api_key() -> None:
    client = build_client()

    response = client.get("/private", headers={"X-API-Key": "expected-secret"})

    assert response.status_code == 200
    assert response.json() == {"ok": "true"}
