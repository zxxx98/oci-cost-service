from datetime import UTC, datetime


def current_utc_month_range(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = now or datetime.now(UTC)
    current = current.astimezone(UTC)
    started = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ended = current.replace(hour=0, minute=0, second=0, microsecond=0)
    return started, ended


def month_key(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m")


def iso_z(value: datetime) -> str:
    normalized = value.astimezone(UTC).replace(microsecond=0)
    return normalized.isoformat().replace("+00:00", "Z")
