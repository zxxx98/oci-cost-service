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
