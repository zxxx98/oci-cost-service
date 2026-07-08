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
