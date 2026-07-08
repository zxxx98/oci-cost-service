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
