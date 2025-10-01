from datetime import datetime, timedelta, timezone
from http import HTTPStatus

from flask.testing import FlaskClient

from greektax.backend.app.routes import summaries
from greektax.backend.app.services.share_service import (
    ExpiryFeedbackCollector,
    InMemoryShareRepository,
)

SAMPLE_RESULT = {
    "summary": {
        "income_total": 1000.0,
        "tax_total": 220.0,
        "net_income": 780.0,
        "labels": {
            "income_total": "Total income",
            "tax_total": "Total taxes",
            "net_income": "Net income",
        },
    },
    "details": [
        {
            "category": "employment",
            "label": "Employment income",
            "gross_income": 1000.0,
            "tax": 220.0,
            "total_tax": 220.0,
            "net_income": 780.0,
        }
    ],
    "meta": {"year": 2024, "locale": "en"},
}


def test_create_and_fetch_summary(client: FlaskClient) -> None:
    response = client.post("/api/v1/summaries", json={"result": SAMPLE_RESULT})
    assert response.status_code == HTTPStatus.CREATED

    payload = response.get_json()
    share_id = payload["id"]
    assert "links" in payload
    assert payload["links"]["share_page"].startswith("/share/")
    expires_at = payload["meta"]["expires_at"]
    expiry_timestamp = datetime.fromisoformat(expires_at)
    assert expiry_timestamp.tzinfo is not None

    fetch_response = client.get(f"/api/v1/summaries/{share_id}")
    assert fetch_response.status_code == HTTPStatus.OK
    assert fetch_response.get_json()["meta"]["year"] == 2024

    html_response = client.get(f"/api/v1/summaries/{share_id}/html")
    assert html_response.status_code == HTTPStatus.OK
    assert "Employment income" in html_response.get_data(as_text=True)

    csv_response = client.get(f"/api/v1/summaries/{share_id}/csv")
    assert csv_response.status_code == HTTPStatus.OK
    assert "text/csv" in (csv_response.content_type or "")

    pdf_response = client.get(f"/api/v1/summaries/{share_id}/pdf")
    assert pdf_response.status_code == HTTPStatus.OK
    assert pdf_response.data.startswith(b"%PDF")

    page_response = client.get(payload["links"]["share_page"])
    assert page_response.status_code == HTTPStatus.OK
    assert "Employment income" in page_response.get_data(as_text=True)


def test_create_summary_rejects_invalid_payload(client: FlaskClient) -> None:
    response = client.post("/api/v1/summaries", json={"result": 123})

    assert response.status_code == HTTPStatus.BAD_REQUEST
    data = response.get_json()
    assert data["error"] == "invalid_payload"


def test_summary_not_found(client: FlaskClient) -> None:
    response = client.get("/api/v1/summaries/unknown")
    assert response.status_code == HTTPStatus.NOT_FOUND

    page_response = client.get("/share/unknown")
    assert page_response.status_code == HTTPStatus.NOT_FOUND


def test_summary_expires_after_ttl(client: FlaskClient, monkeypatch) -> None:
    class FixedClock:
        def __init__(self, start: datetime) -> None:
            self.current = start

        def advance(self, delta: timedelta) -> None:
            self.current += delta

        def __call__(self) -> datetime:
            return self.current

    clock = FixedClock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    repository = InMemoryShareRepository(ttl_seconds=60, clock=clock)
    monkeypatch.setattr(summaries, "_REPOSITORY", repository)

    response = client.post("/api/v1/summaries", json={"result": SAMPLE_RESULT})
    assert response.status_code == HTTPStatus.CREATED
    share_id = response.get_json()["id"]

    # Fresh record is retrievable before the TTL elapses.
    assert client.get(f"/api/v1/summaries/{share_id}").status_code == HTTPStatus.OK

    # Once the TTL passes the record should disappear.
    clock.advance(timedelta(seconds=61))
    assert client.get(f"/api/v1/summaries/{share_id}").status_code == HTTPStatus.NOT_FOUND


def test_submit_feedback_records_response(client: FlaskClient, monkeypatch) -> None:
    repository = InMemoryShareRepository(ttl_seconds=None)
    collector = ExpiryFeedbackCollector()
    monkeypatch.setattr(summaries, "_REPOSITORY", repository)
    monkeypatch.setattr(summaries, "_FEEDBACK_COLLECTOR", collector)

    response = client.post("/api/v1/summaries", json={"result": SAMPLE_RESULT})
    share_id = response.get_json()["id"]

    feedback_response = client.post(
        f"/api/v1/summaries/{share_id}/feedback",
        json={"clarity": "clear", "notes": "Great context"},
    )
    assert feedback_response.status_code == HTTPStatus.ACCEPTED
    payload = feedback_response.get_json()
    assert payload["summary"]["clarity"]["clear"] == 1
    assert payload["summary"]["total_responses"] == 1

    summary_response = client.get("/api/v1/summaries/feedback/summary")
    assert summary_response.status_code == HTTPStatus.OK
    assert summary_response.get_json()["clarity"]["clear"] == 1


def test_submit_feedback_validates_payload(client: FlaskClient, monkeypatch) -> None:
    repository = InMemoryShareRepository(ttl_seconds=None)
    collector = ExpiryFeedbackCollector()
    monkeypatch.setattr(summaries, "_REPOSITORY", repository)
    monkeypatch.setattr(summaries, "_FEEDBACK_COLLECTOR", collector)

    response = client.post("/api/v1/summaries", json={"result": SAMPLE_RESULT})
    share_id = response.get_json()["id"]

    bad_response = client.post(f"/api/v1/summaries/{share_id}/feedback", json={"clarity": 123})
    assert bad_response.status_code == HTTPStatus.BAD_REQUEST

    too_long = "a" * 501
    invalid_notes = client.post(
        f"/api/v1/summaries/{share_id}/feedback",
        json={"clarity": "clear", "notes": too_long},
    )
    assert invalid_notes.status_code == HTTPStatus.BAD_REQUEST
