from datetime import UTC, datetime

from app.time_utils import current_utc_month_range, iso_z, month_key


def test_current_utc_month_range() -> None:
    now = datetime(2026, 7, 8, 15, 30, 45, tzinfo=UTC)

    started, ended = current_utc_month_range(now)

    assert started == datetime(2026, 7, 1, 0, 0, 0, tzinfo=UTC)
    assert ended == datetime(2026, 7, 8, 0, 0, 0, tzinfo=UTC)


def test_month_key() -> None:
    assert month_key(datetime(2026, 7, 8, tzinfo=UTC)) == "2026-07"


def test_iso_z() -> None:
    assert iso_z(datetime(2026, 7, 8, 15, 30, 45, tzinfo=UTC)) == "2026-07-08T15:30:45Z"
