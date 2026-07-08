from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    billing_api_key: str = Field(alias="BILLING_API_KEY")
    oci_auth: Literal["instance_principal"] = Field(
        default="instance_principal",
        alias="OCI_AUTH",
    )
    cache_ttl_seconds: int = Field(default=1800, alias="CACHE_TTL_SECONDS", ge=1)
    port: int = Field(default=8000, alias="PORT", ge=1, le=65535)
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("billing_api_key")
    @classmethod
    def api_key_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("BILLING_API_KEY must not be empty")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
