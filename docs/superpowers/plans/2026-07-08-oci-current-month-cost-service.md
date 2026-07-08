# OCI Current Month Cost Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Dockerized FastAPI service that runs on an OCI Compute instance, uses Instance Principal authentication, and exposes API-key-protected endpoints for current-month OCI costs.

**Architecture:** The service is split into focused modules: configuration, HTTP API, API-key auth, billing aggregation, OCI Usage API access, and in-memory caching. FastAPI handlers authenticate requests, call the billing service, and return normalized JSON responses; the billing service computes the current UTC month range and delegates OCI calls to a gateway wrapper around the OCI Python SDK.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, OCI Python SDK, Pydantic Settings, pytest, Docker, docker compose.

---

## File Structure

- Create `pyproject.toml`: project metadata, runtime dependencies, test dependencies, pytest config.
- Create `app/__init__.py`: marks the application package.
- Create `app/config.py`: environment-based settings and startup validation.
- Create `app/auth.py`: `X-API-Key` FastAPI dependency using constant-time comparison.
- Create `app/time_utils.py`: current UTC month range helpers.
- Create `app/cache.py`: simple TTL cache used by billing queries.
- Create `app/oci_usage.py`: OCI SDK client factory and Usage API request wrapper.
- Create `app/billing.py`: cost query orchestration and response shaping.
- Create `app/main.py`: FastAPI app and route definitions.
- Create `tests/conftest.py`: shared pytest fixtures.
- Create `tests/test_config.py`: settings validation tests.
- Create `tests/test_auth.py`: API key behavior tests.
- Create `tests/test_time_utils.py`: current-month range tests.
- Create `tests/test_cache.py`: TTL cache tests.
- Create `tests/test_billing.py`: aggregation and OCI failure mapping tests.
- Create `tests/test_api.py`: endpoint behavior tests.
- Create `.env.example`: documented environment variables.
- Create `.gitignore`: Python, pytest, venv, env-file ignores.
- Create `Dockerfile`: production container image.
- Create `docker-compose.yml`: server deployment definition.
- Create `README.md`: setup, IAM, deployment, and curl examples.

## Task 1: Project Baseline And Configuration

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `tests/test_config.py`
- Create: `.gitignore`

- [ ] **Step 1: Write configuration tests**

Create `tests/test_config.py`:

```python
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
    assert settings.port == 8000
    assert settings.log_level == "INFO"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_config.py -v
```

Expected: FAIL because `app.config` does not exist.

- [ ] **Step 3: Add project metadata**

Create `pyproject.toml`:

```toml
[project]
name = "oci-current-month-cost-service"
version = "0.1.0"
description = "Dockerized FastAPI service for current-month OCI costs"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.111.0",
  "oci>=2.126.0",
  "pydantic-settings>=2.3.0",
  "uvicorn[standard]>=0.30.0",
]

[project.optional-dependencies]
test = [
  "httpx>=0.27.0",
  "pytest>=8.2.0",
  "pytest-mock>=3.14.0",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

Create `.gitignore`:

```gitignore
.env
.venv/
__pycache__/
.pytest_cache/
*.pyc
```

Create `app/__init__.py`:

```python
```

- [ ] **Step 4: Implement settings**

Create `app/config.py`:

```python
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
```

- [ ] **Step 5: Run configuration tests**

Run:

```bash
python -m pytest tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit baseline**

Run:

```bash
git add pyproject.toml .gitignore app/__init__.py app/config.py tests/test_config.py
git commit -m "chore: add project configuration"
```

Expected: commit succeeds when the workspace is a git repository. If it is not, initialize it first with `git init`.

## Task 2: API Key Authentication And Health Endpoint

**Files:**
- Create: `app/auth.py`
- Create: `app/main.py`
- Create: `tests/test_auth.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write authentication tests**

Create `tests/test_auth.py`:

```python
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

    app.dependency_overrides = {}
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
```

Create `tests/test_api.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_is_public() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_auth.py tests/test_api.py -v
```

Expected: FAIL because `app.auth` and `app.main` are incomplete or missing.

- [ ] **Step 3: Implement API key dependency**

Create `app/auth.py`:

```python
import hmac

from fastapi import Header, HTTPException, Request, status

from app.config import get_settings


def _configured_key(request: Request) -> str:
    override = getattr(request.app.state, "settings_override", None)
    if override is not None:
        return override().billing_api_key
    return get_settings().billing_api_key


def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    expected = _configured_key(request)
    provided = x_api_key or ""

    if not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )
```

- [ ] **Step 4: Implement FastAPI app and health endpoint**

Create `app/main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="OCI Current Month Cost Service")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Run authentication and health tests**

Run:

```bash
python -m pytest tests/test_auth.py tests/test_api.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit authentication and health endpoint**

Run:

```bash
git add app/auth.py app/main.py tests/test_auth.py tests/test_api.py
git commit -m "feat: add api key auth and health endpoint"
```

Expected: commit succeeds.

## Task 3: Time Range And TTL Cache

**Files:**
- Create: `app/time_utils.py`
- Create: `app/cache.py`
- Create: `tests/test_time_utils.py`
- Create: `tests/test_cache.py`

- [ ] **Step 1: Write time utility tests**

Create `tests/test_time_utils.py`:

```python
from datetime import UTC, datetime

from app.time_utils import current_utc_month_range, iso_z, month_key


def test_current_utc_month_range() -> None:
    now = datetime(2026, 7, 8, 15, 30, 45, tzinfo=UTC)

    started, ended = current_utc_month_range(now)

    assert started == datetime(2026, 7, 1, 0, 0, 0, tzinfo=UTC)
    assert ended == now


def test_month_key() -> None:
    assert month_key(datetime(2026, 7, 8, tzinfo=UTC)) == "2026-07"


def test_iso_z() -> None:
    assert iso_z(datetime(2026, 7, 8, 15, 30, 45, tzinfo=UTC)) == "2026-07-08T15:30:45Z"
```

- [ ] **Step 2: Write cache tests**

Create `tests/test_cache.py`:

```python
from datetime import UTC, datetime, timedelta

from app.cache import TTLCache


def test_cache_miss_when_key_absent() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=30)

    assert cache.get("missing", now=datetime(2026, 7, 8, tzinfo=UTC)) is None


def test_cache_hit_before_expiry() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=30)
    now = datetime(2026, 7, 8, 0, 0, tzinfo=UTC)

    cache.set("key", "value", now=now)

    assert cache.get("key", now=now + timedelta(seconds=29)) == "value"


def test_cache_miss_after_expiry() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=30)
    now = datetime(2026, 7, 8, 0, 0, tzinfo=UTC)

    cache.set("key", "value", now=now)

    assert cache.get("key", now=now + timedelta(seconds=31)) is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_time_utils.py tests/test_cache.py -v
```

Expected: FAIL because `app.time_utils` and `app.cache` do not exist.

- [ ] **Step 4: Implement time utilities**

Create `app/time_utils.py`:

```python
from datetime import UTC, datetime


def current_utc_month_range(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = now or datetime.now(UTC)
    current = current.astimezone(UTC)
    started = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return started, current


def month_key(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m")


def iso_z(value: datetime) -> str:
    normalized = value.astimezone(UTC).replace(microsecond=0)
    return normalized.isoformat().replace("+00:00", "Z")
```

- [ ] **Step 5: Implement TTL cache**

Create `app/cache.py`:

```python
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class CacheEntry(Generic[T]):
    value: T
    expires_at: datetime


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._entries: dict[str, CacheEntry[T]] = {}

    def get(self, key: str, now: datetime | None = None) -> T | None:
        current = now or datetime.now(UTC)
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= current:
            self._entries.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: T, now: datetime | None = None) -> None:
        current = now or datetime.now(UTC)
        self._entries[key] = CacheEntry(value=value, expires_at=current + self._ttl)
```

- [ ] **Step 6: Run time and cache tests**

Run:

```bash
python -m pytest tests/test_time_utils.py tests/test_cache.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit time and cache modules**

Run:

```bash
git add app/time_utils.py app/cache.py tests/test_time_utils.py tests/test_cache.py
git commit -m "feat: add time range and ttl cache helpers"
```

Expected: commit succeeds.

## Task 4: OCI Usage API Gateway

**Files:**
- Create: `app/oci_usage.py`
- Create: `tests/test_oci_usage.py`

- [ ] **Step 1: Write OCI gateway tests**

Create `tests/test_oci_usage.py`:

```python
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
    gateway = UsageGateway(fake_client)
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
    assert fake_client.request.granularity == "DAILY"
    assert fake_client.request.query_type == "COST"
    assert fake_client.request.group_by == ["service"]
```

- [ ] **Step 2: Run gateway test to verify it fails**

Run:

```bash
python -m pytest tests/test_oci_usage.py -v
```

Expected: FAIL because `app.oci_usage` does not exist.

- [ ] **Step 3: Implement OCI gateway**

Create `app/oci_usage.py`:

```python
from datetime import datetime
from typing import Any, Literal

import oci
from oci.usage_api.models import RequestSummarizedUsagesDetails


Granularity = Literal["DAILY", "MONTHLY"]


class UsageGateway:
    def __init__(self, client: Any) -> None:
        self._client = client

    def request_costs(
        self,
        *,
        started: datetime,
        ended: datetime,
        granularity: Granularity,
        group_by: list[str] | None = None,
    ) -> list[Any]:
        details = RequestSummarizedUsagesDetails(
            time_usage_started=started,
            time_usage_ended=ended,
            granularity=granularity,
            query_type="COST",
            group_by=group_by or [],
        )
        response = self._client.request_summarized_usages(details)
        return list(response.data.items or [])


def build_instance_principal_gateway() -> UsageGateway:
    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
    client = oci.usage_api.UsageapiClient(config={}, signer=signer)
    return UsageGateway(client)
```

- [ ] **Step 4: Run OCI gateway test**

Run:

```bash
python -m pytest tests/test_oci_usage.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit OCI gateway**

Run:

```bash
git add app/oci_usage.py tests/test_oci_usage.py
git commit -m "feat: add oci usage gateway"
```

Expected: commit succeeds.

## Task 5: Billing Service Aggregation

**Files:**
- Create: `app/billing.py`
- Create: `tests/test_billing.py`

- [ ] **Step 1: Write billing aggregation tests**

Create `tests/test_billing.py`:

```python
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

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
    assert response["timeUsageEnded"] == "2026-07-08T12:00:00Z"
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
```

- [ ] **Step 2: Run billing tests to verify they fail**

Run:

```bash
python -m pytest tests/test_billing.py -v
```

Expected: FAIL because `app.billing` does not exist.

- [ ] **Step 3: Implement billing service**

Create `app/billing.py`:

```python
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

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
        return self._cached("month_by_service", current, lambda: self._grouped(current, ["service"], "service"))

    def month_by_resource(self, now: datetime | None = None) -> dict[str, Any]:
        current = now or datetime.now(UTC)
        return self._cached("month_by_resource", current, lambda: self._resources(current))

    def month_daily(self, now: datetime | None = None) -> dict[str, Any]:
        current = now or datetime.now(UTC)
        return self._cached("month_daily", current, lambda: self._daily(current))

    def _cached(self, key: str, now: datetime, factory) -> dict[str, Any]:
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
```

- [ ] **Step 4: Run billing tests**

Run:

```bash
python -m pytest tests/test_billing.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit billing service**

Run:

```bash
git add app/billing.py tests/test_billing.py
git commit -m "feat: add billing aggregation service"
```

Expected: commit succeeds.

## Task 6: Cost API Endpoints

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Extend API tests**

Replace `tests/test_api.py` with:

```python
from oci.exceptions import ServiceError
from fastapi.testclient import TestClient

from app.main import app, get_billing_service, validate_startup_settings


class FakeBillingService:
    def month_total(self):
        return {"month": "2026-07", "currency": "USD", "total": 1.23, "cached": False, "lastFetchedAt": "2026-07-08T00:00:00Z"}

    def month_by_service(self):
        return {"month": "2026-07", "currency": "USD", "items": [{"service": "Compute", "total": 1.23}], "cached": False, "lastFetchedAt": "2026-07-08T00:00:00Z"}

    def month_by_resource(self):
        return {"month": "2026-07", "currency": "USD", "items": [{"resourceId": "ocid1.instance.example", "service": "Compute", "total": 1.23}], "cached": False, "lastFetchedAt": "2026-07-08T00:00:00Z"}

    def month_daily(self):
        return {"month": "2026-07", "currency": "USD", "items": [{"date": "2026-07-01", "total": 1.23}], "cached": False, "lastFetchedAt": "2026-07-08T00:00:00Z"}


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
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```bash
python -m pytest tests/test_api.py -v
```

Expected: FAIL because cost endpoints are missing.

- [ ] **Step 3: Implement cost endpoints**

Replace `app/main.py` with:

```python
import logging
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any, Callable

from fastapi import Depends, FastAPI, HTTPException, status
from oci.exceptions import ServiceError

from app.auth import require_api_key
from app.billing import BillingService
from app.cache import TTLCache
from app.config import get_settings
from app.oci_usage import build_instance_principal_gateway

logger = logging.getLogger(__name__)


def validate_startup_settings() -> None:
    get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    override = app.dependency_overrides.get(validate_startup_settings)
    if override is not None:
        override()
    else:
        validate_startup_settings()
    yield


app = FastAPI(title="OCI Current Month Cost Service", lifespan=lifespan)


@lru_cache
def get_billing_service() -> BillingService:
    settings = get_settings()
    gateway = build_instance_principal_gateway()
    cache: TTLCache[dict[str, Any]] = TTLCache(ttl_seconds=settings.cache_ttl_seconds)
    return BillingService(gateway=gateway, cache=cache)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _billing_response(operation: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return operation()
    except ServiceError:
        logger.exception("OCI Usage API request failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OCI Usage API error",
        )
    except Exception:
        logger.exception("Unexpected billing request failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@app.get("/cost/month", dependencies=[Depends(require_api_key)])
def cost_month(service: BillingService = Depends(get_billing_service)) -> dict[str, Any]:
    return _billing_response(service.month_total)


@app.get("/cost/month/by-service", dependencies=[Depends(require_api_key)])
def cost_month_by_service(service: BillingService = Depends(get_billing_service)) -> dict[str, Any]:
    return _billing_response(service.month_by_service)


@app.get("/cost/month/by-resource", dependencies=[Depends(require_api_key)])
def cost_month_by_resource(service: BillingService = Depends(get_billing_service)) -> dict[str, Any]:
    return _billing_response(service.month_by_resource)


@app.get("/cost/month/daily", dependencies=[Depends(require_api_key)])
def cost_month_daily(service: BillingService = Depends(get_billing_service)) -> dict[str, Any]:
    return _billing_response(service.month_daily)
```

- [ ] **Step 4: Run API tests**

Run:

```bash
python -m pytest tests/test_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Run the full test suite**

Run:

```bash
python -m pytest -v
```

Expected: PASS.

- [ ] **Step 6: Commit API endpoints**

Run:

```bash
git add app/main.py tests/test_api.py
git commit -m "feat: expose current month cost endpoints"
```

Expected: commit succeeds.

## Task 7: Docker Packaging And Runtime Docs

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `README.md`

- [ ] **Step 1: Add environment example**

Create `.env.example`:

```env
BILLING_API_KEY=replace-with-a-long-random-secret
OCI_AUTH=instance_principal
CACHE_TTL_SECONDS=1800
PORT=8000
LOG_LEVEL=INFO
```

- [ ] **Step 2: Add Dockerfile**

Create `Dockerfile`:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[test]"

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Add docker compose deployment**

Create `docker-compose.yml`:

```yaml
services:
  oci-cost-service:
    build: .
    container_name: oci-cost-service
    env_file:
      - .env
    ports:
      - "8000:8000"
    restart: unless-stopped
```

- [ ] **Step 4: Add README**

Create `README.md`:

```markdown
# OCI Current Month Cost Service

Dockerized FastAPI service for querying the current UTC month's OCI cost.

## Configuration

Copy `.env.example` to `.env` and set a long random `BILLING_API_KEY`.

```env
BILLING_API_KEY=replace-with-a-long-random-secret
OCI_AUTH=instance_principal
CACHE_TTL_SECONDS=1800
PORT=8000
LOG_LEVEL=INFO
```

## OCI IAM

Deploy this service on an OCI Compute instance and use Instance Principal
authentication. Create a Dynamic Group that matches the instance, then grant the
group permission to read tenancy cost and usage data required by OCI Usage API.

Verify the exact policy statement in the target tenancy's Billing and Cost
Management IAM documentation before production use.

## Run

```bash
docker compose up -d --build
```

## Check

```bash
curl http://SERVER_IP:8000/health
curl -H "X-API-Key: $BILLING_API_KEY" http://SERVER_IP:8000/cost/month
curl -H "X-API-Key: $BILLING_API_KEY" http://SERVER_IP:8000/cost/month/by-service
curl -H "X-API-Key: $BILLING_API_KEY" http://SERVER_IP:8000/cost/month/by-resource
curl -H "X-API-Key: $BILLING_API_KEY" http://SERVER_IP:8000/cost/month/daily
```

## Security

The initial deployment exposes port 8000 directly and uses `X-API-Key` for
application authentication. For public production use, put the service behind
HTTPS termination with Caddy, Nginx, an OCI Load Balancer, or another TLS proxy.
```

- [ ] **Step 5: Build Docker image**

Run:

```bash
docker compose build
```

Expected: image builds successfully.

- [ ] **Step 6: Verify container refuses missing API key**

Run:

```bash
docker compose run --rm -e BILLING_API_KEY= oci-cost-service
```

Expected: process exits during startup because `BILLING_API_KEY` is missing.

- [ ] **Step 7: Commit Docker packaging**

Run:

```bash
git add Dockerfile docker-compose.yml .env.example README.md
git commit -m "chore: add docker deployment files"
```

Expected: commit succeeds.

## Task 8: Final Verification And Server Integration Checklist

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run full local tests**

Run:

```bash
python -m pytest -v
```

Expected: PASS.

- [ ] **Step 2: Run Docker build**

Run:

```bash
docker compose build
```

Expected: PASS.

- [ ] **Step 3: Start service with test key**

Run:

```bash
cp .env.example .env
sed -i 's/replace-with-a-long-random-secret/local-test-secret/' .env
docker compose up -d
```

Expected: container starts.

- [ ] **Step 4: Verify public health endpoint**

Run:

```bash
curl -s http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok"}
```

- [ ] **Step 5: Verify cost endpoint rejects missing key**

Run:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/cost/month
```

Expected:

```text
401
```

- [ ] **Step 6: Verify cost endpoint attempts OCI with valid key**

Run on the OCI Compute instance after Dynamic Group and IAM policy setup:

```bash
curl -s -H "X-API-Key: local-test-secret" http://127.0.0.1:8000/cost/month
```

Expected: JSON response with `month`, `currency`, `total`, `cached`, and
`lastFetchedAt`. If IAM is not configured, the response or logs should show an
OCI authorization error.

- [ ] **Step 7: Stop local deployment**

Run:

```bash
docker compose down
```

Expected: container stops.

- [ ] **Step 8: Commit verification documentation if README changed**

Run:

```bash
git add README.md
git commit -m "docs: add deployment verification steps"
```

Expected: commit succeeds when README changes exist. If README is unchanged,
`git status --short` shows no tracked README diff and no commit is needed.

## Self-Review

- Spec coverage: The plan covers Docker deployment, public API, `X-API-Key`
  authentication, Instance Principal production auth, current-month total cost,
  service breakdown, resource breakdown, daily trend, caching, health checks,
  tests, and manual OCI integration verification.
- Placeholder scan: No unresolved placeholder markers or deferred
  implementation notes are present.
- Type consistency: `BillingService`, `TTLCache`, `UsageGateway`,
  `require_api_key`, and `get_billing_service` are introduced before use and use
  consistent names across tests and implementation steps.
