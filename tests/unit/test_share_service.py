from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from greektax.backend.app.services.share_service import (
    ExpiryFeedbackCollector,
    InMemoryShareRepository,
    SQLiteShareRepository,
    ShareRecord,
    render_pdf,
)


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self.current = start

    def advance(self, delta: timedelta) -> None:
        self.current += delta

    def __call__(self) -> datetime:
        return self.current


def test_repository_honours_ttl() -> None:
    clock = FakeClock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    repository = InMemoryShareRepository(ttl_seconds=60, clock=clock)

    record = repository.save({"meta": {"locale": "el"}})
    assert record.locale == "el"
    assert record.expires_at - record.created_at == timedelta(seconds=60)

    clock.advance(timedelta(seconds=61))
    with pytest.raises(KeyError):
        repository.get(record.id)


def test_repository_enforces_capacity() -> None:
    clock = FakeClock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    repository = InMemoryShareRepository(ttl_seconds=None, max_items=2, clock=clock)

    first = repository.save({"meta": {"locale": "en"}})
    second = repository.save({"meta": {"locale": "el"}})
    third = repository.save({"meta": {"locale": "en"}})

    with pytest.raises(KeyError):
        repository.get(first.id)

    assert repository.get(second.id).id == second.id
    assert repository.get(third.id).id == third.id


def test_sqlite_repository_persists_records(tmp_path: Path) -> None:
    db_path = tmp_path / "shares.db"
    repository = SQLiteShareRepository(db_path, ttl_seconds=None, max_items=10)

    record = repository.save({"meta": {"locale": "el"}, "summary": {"income_total": 123}})

    # A fresh repository instance should read the persisted record.
    fresh = SQLiteShareRepository(db_path, ttl_seconds=None, max_items=10)
    retrieved = fresh.get(record.id)
    assert retrieved.payload["summary"]["income_total"] == 123
    assert retrieved.locale == "el"


def test_sqlite_repository_honours_ttl(tmp_path: Path) -> None:
    clock = FakeClock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    repository = SQLiteShareRepository(tmp_path / "shares.db", ttl_seconds=60, clock=clock)

    record = repository.save({"meta": {"locale": "en"}})
    assert repository.get(record.id).id == record.id

    clock.advance(timedelta(seconds=61))
    with pytest.raises(KeyError):
        repository.get(record.id)


def test_sqlite_repository_enforces_capacity(tmp_path: Path) -> None:
    clock = FakeClock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    repository = SQLiteShareRepository(
        tmp_path / "shares.db",
        ttl_seconds=None,
        max_items=2,
        clock=clock,
    )

    first = repository.save({"meta": {"locale": "en"}})
    second = repository.save({"meta": {"locale": "el"}})
    third = repository.save({"meta": {"locale": "en"}})

    with pytest.raises(KeyError):
        repository.get(first.id)

    assert repository.get(second.id).id == second.id
    assert repository.get(third.id).id == third.id


def test_sqlite_repository_is_thread_safe(tmp_path: Path) -> None:
    repository = SQLiteShareRepository(tmp_path / "shares.db", ttl_seconds=None, max_items=200)

    def worker(index: int) -> str:
        record = repository.save({"meta": {"locale": "en"}, "index": index})
        fetched = repository.get(record.id)
        assert fetched.payload["index"] == index
        return record.id

    with ThreadPoolExecutor(max_workers=4) as executor:
        ids = list(executor.map(worker, range(12)))

    assert len(set(ids)) == 12


def test_expiry_feedback_collector_tracks_totals() -> None:
    collector = ExpiryFeedbackCollector(capacity=3)
    collector.submit(share_id="a", clarity="clear", locale="en")
    collector.submit(share_id="b", clarity="unclear", locale="el", notes="Needs clearer contrast")
    collector.submit(share_id="c", clarity="unclear", locale="en")
    collector.submit(share_id="d", clarity="clear", locale="el")  # pushes out the oldest entry

    summary = collector.summary()
    assert summary["total_responses"] == 3
    assert summary["clarity"]["clear"] == 1
    assert summary["clarity"]["unclear"] == 2
    assert summary["by_locale"]["el"]["unclear"] == 1
    assert any("contrast" in entry["notes"] for entry in summary["recent_notes"])


def test_render_pdf_supports_greek_and_multiple_pages() -> None:
    payload = {
        "summary": {
            "income_total": 2000,
            "tax_total": 400,
            "net_income": 1600,
        },
        "details": [
            {
                "label": f"Εισόδημα {index}",
                "gross_income": 100 + index,
                "tax": 20 + index,
                "total_tax": 20 + index,
                "net_income": 80 + index,
                "items": [
                    {
                        "label": f"Κατηγορία {index}-{item}",
                        "amount": 100 + item,
                        "tax": 10 + item,
                        "rate": 0.2,
                    }
                    for item in range(5)
                ],
            }
            for index in range(12)
        ],
        "meta": {"locale": "el"},
    }
    record = ShareRecord(
        id="test",
        payload=payload,
        locale="el",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        expires_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )

    pdf_bytes = render_pdf(record)
    assert pdf_bytes.startswith(b"%PDF")
    assert pdf_bytes.count(b"/Type /Page") >= 2
    assert b"NotoSans" in pdf_bytes
