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
