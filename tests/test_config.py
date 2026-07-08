import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_require_billing_api_key() -> None:
    with pytest.raises(ValidationError):
        Settings(BILLING_API_KEY="")


def test_settings_defaults() -> None:
    settings = Settings(BILLING_API_KEY="secret-value")

    assert settings.billing_api_key == "secret-value"
    assert settings.oci_auth == "instance_principal"
    assert settings.cache_ttl_seconds == 1800
    assert settings.nezha_server_id is None
    assert settings.port == 8000
    assert settings.log_level == "INFO"


def test_settings_accept_nezha_server_id() -> None:
    settings = Settings(BILLING_API_KEY="secret-value", NEZHA_SERVER_ID=1)

    assert settings.nezha_server_id == 1
