"""Helpers for persisting and exporting shareable calculation summaries."""

from __future__ import annotations

import csv
import json
import os
import sqlite3
from collections import Counter, OrderedDict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import StringIO
from threading import Lock
from typing import Any, Callable, Deque, Dict, Iterable, List, Mapping, Sequence
from uuid import uuid4

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from greektax.backend.app.localization import Translator, get_translator
from greektax.backend.app.services.fonts import ensure_noto_sans

_DETAIL_FIELD_LABEL_KEYS: Dict[str, str] = {
    "gross_income": "share.detail_fields.gross_income",
    "deductible_contributions": "share.detail_fields.deductible_contributions",
    "deductible_expenses": "share.detail_fields.deductible_expenses",
    "taxable_income": "share.detail_fields.taxable_income",
    "tax_before_credits": "share.detail_fields.tax_before_credits",
    "credits": "share.detail_fields.credits",
    "tax": "share.detail_fields.tax",
    "trade_fee": "share.detail_fields.trade_fee",
    "total_tax": "share.detail_fields.total_tax",
    "net_income": "share.detail_fields.net_income",
}

_MAX_EXPIRY = datetime.max.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class ShareRecord:
    """Persisted snapshot of a calculation result."""

    id: str
    payload: Mapping[str, Any]
    locale: str
    created_at: datetime
    expires_at: datetime

    def is_expired(self, *, now: datetime | None = None) -> bool:
        """Return ``True`` when the record has passed its expiry timestamp."""

        reference = now or datetime.now(timezone.utc)
        return reference >= self.expires_at


class InMemoryShareRepository:
    """Thread-safe in-memory storage for shareable summaries with TTL support."""

    def __init__(
        self,
        *,
        ttl_seconds: int | None = 60 * 60 * 24,
        max_items: int | None = 500,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if ttl_seconds is not None and ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive when provided")
        if max_items is not None and max_items <= 0:
            raise ValueError("max_items must be positive when provided")

        self._ttl = timedelta(seconds=ttl_seconds) if ttl_seconds is not None else None
        self._max_items = max_items
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._records: "OrderedDict[str, ShareRecord]" = OrderedDict()
        self._lock = Lock()

    def _cleanup_locked(self, now: datetime) -> None:
        if self._ttl is not None:
            expired_keys = [
                key for key, record in self._records.items() if record.expires_at <= now
            ]
            for key in expired_keys:
                self._records.pop(key, None)

        if self._max_items is not None:
            while len(self._records) > self._max_items:
                self._records.popitem(last=False)

    def save(self, payload: Mapping[str, Any]) -> ShareRecord:
        share_id = uuid4().hex
        meta = payload.get("meta", {}) if isinstance(payload, Mapping) else {}
        locale = str(meta.get("locale", "en"))
        now = self._clock()
        expires_at = now + self._ttl if self._ttl is not None else _MAX_EXPIRY
        record = ShareRecord(
            id=share_id,
            payload=payload,
            locale=locale,
            created_at=now,
            expires_at=expires_at,
        )
        with self._lock:
            self._cleanup_locked(now)
            self._records[share_id] = record
            self._records.move_to_end(share_id)
            self._cleanup_locked(now)
        return record

    def get(self, share_id: str) -> ShareRecord:
        now = self._clock()
        with self._lock:
            self._cleanup_locked(now)
            record = self._records.get(share_id)
            if record is None or record.is_expired(now=now):
                if record is not None:
                    self._records.pop(share_id, None)
                raise KeyError(share_id)
            return record


class SQLiteShareRepository:
    """SQLite-backed repository providing persistence and TTL enforcement."""

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        ttl_seconds: int | None = 60 * 60 * 24,
        max_items: int | None = 2000,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if ttl_seconds is not None and ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive when provided")
        if max_items is not None and max_items <= 0:
            raise ValueError("max_items must be positive when provided")

        self._path = str(path)
        self._ttl = timedelta(seconds=ttl_seconds) if ttl_seconds is not None else None
        self._max_items = max_items
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = Lock()
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._path,
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
        )
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _initialise(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS shares (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    locale TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )

    def _cleanup_locked(self, connection: sqlite3.Connection, now: datetime) -> None:
        if self._ttl is not None:
            connection.execute(
                "DELETE FROM shares WHERE expires_at <= ?",
                (now.isoformat(),),
            )
        if self._max_items is not None:
            excess = connection.execute(
                "SELECT COUNT(*) - ? FROM shares",
                (self._max_items,),
            ).fetchone()[0]
            if excess is not None and excess > 0:
                connection.execute(
                    "DELETE FROM shares WHERE id IN ("
                    "SELECT id FROM shares ORDER BY created_at ASC LIMIT ?"
                    ")",
                    (excess,),
                )

    @staticmethod
    def _decode_record(row: sqlite3.Row) -> ShareRecord:
        payload = json.loads(row["payload"])
        created_at = datetime.fromisoformat(row["created_at"])
        expires_at = datetime.fromisoformat(row["expires_at"])
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return ShareRecord(
            id=row["id"],
            payload=payload,
            locale=row["locale"],
            created_at=created_at,
            expires_at=expires_at,
        )

    def save(self, payload: Mapping[str, Any]) -> ShareRecord:
        share_id = uuid4().hex
        meta = payload.get("meta", {}) if isinstance(payload, Mapping) else {}
        locale = str(meta.get("locale", "en"))
        now = self._clock()
        expires_at = now + self._ttl if self._ttl is not None else _MAX_EXPIRY
        record = ShareRecord(
            id=share_id,
            payload=payload,
            locale=locale,
            created_at=now,
            expires_at=expires_at,
        )

        payload_json = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            with self._connect() as connection:
                connection.row_factory = sqlite3.Row
                self._cleanup_locked(connection, now)
                connection.execute(
                    "INSERT INTO shares (id, payload, locale, created_at, expires_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (
                        record.id,
                        payload_json,
                        record.locale,
                        record.created_at.isoformat(),
                        record.expires_at.isoformat(),
                    ),
                )
        return record

    def get(self, share_id: str) -> ShareRecord:
        now = self._clock()
        with self._lock:
            with self._connect() as connection:
                connection.row_factory = sqlite3.Row
                self._cleanup_locked(connection, now)
                row = connection.execute(
                    "SELECT * FROM shares WHERE id = ?",
                    (share_id,),
                ).fetchone()
                if row is None:
                    raise KeyError(share_id)
                record = self._decode_record(row)
                if record.is_expired(now=now):
                    connection.execute("DELETE FROM shares WHERE id = ?", (share_id,))
                    raise KeyError(share_id)
                return record


class ExpiryFeedbackCollector:
    """Collect lightweight user feedback for expiry messaging."""

    def __init__(self, *, capacity: int = 500) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._entries: Deque[dict[str, Any]] = deque(maxlen=capacity)
        self._lock = Lock()

    def submit(self, *, share_id: str, clarity: str, locale: str, notes: str | None = None) -> None:
        clarity_key = clarity.lower()
        if clarity_key not in {"clear", "unclear"}:
            raise ValueError("clarity must be 'clear' or 'unclear'")

        entry = {
            "share_id": share_id,
            "clarity": clarity_key,
            "locale": locale,
            "notes": notes or "",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._entries.append(entry)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            totals = Counter(entry["clarity"] for entry in self._entries)
            locale_breakdown: Dict[str, Dict[str, int]] = {}
            for entry in self._entries:
                locale_breakdown.setdefault(entry["locale"], {"clear": 0, "unclear": 0})
                locale_breakdown[entry["locale"]][entry["clarity"]] += 1

            recent_notes = [entry for entry in list(self._entries)[-10:] if entry["notes"]]

        return {
            "total_responses": sum(totals.values()),
            "clarity": {"clear": totals.get("clear", 0), "unclear": totals.get("unclear", 0)},
            "by_locale": locale_breakdown,
            "recent_notes": recent_notes,
        }


def _format_currency(value: Any) -> str:
    number = float(value or 0)
    return f"€{number:,.2f}"


def _format_percent(value: Any) -> str:
    number = float(value or 0)
    return f"{number * 100:.1f}%"


def _summary_rows(summary: Mapping[str, Any], translator: Translator) -> Iterable[tuple[str, str]]:
    labels = summary.get("labels", {}) if isinstance(summary, Mapping) else {}
    for key in ("income_total", "tax_total", "net_income"):
        if key in summary:
            label = labels.get(key) or translator(f"summary.{key}")
            yield label, _format_currency(summary[key])


def _detail_rows(detail: Mapping[str, Any], translator: Translator) -> List[tuple[str, str]]:
    rows: List[tuple[str, str]] = []
    for field, label_key in _DETAIL_FIELD_LABEL_KEYS.items():
        if field not in detail:
            continue
        label = translator(label_key)
        value = detail[field]
        if field in {"tax", "total_tax", "gross_income", "taxable_income", "net_income", "deductible_contributions", "deductible_expenses", "trade_fee"}:
            rows.append((label, _format_currency(value)))
        else:
            rows.append((label, str(value)))
    return rows


def _detail_breakdown(detail: Mapping[str, Any], translator: Translator) -> List[str]:
    breakdown = []
    items = detail.get("items")
    if not isinstance(items, Sequence):
        return breakdown
    for item in items:
        if not isinstance(item, Mapping):
            continue
        label = str(item.get("label") or item.get("type") or "")
        amount = _format_currency(item.get("amount", 0))
        tax = _format_currency(item.get("tax", 0))
        rate = item.get("rate")
        if rate is not None:
            breakdown.append(f"{label}: {amount} → {tax} ({_format_percent(rate)})")
        else:
            breakdown.append(f"{label}: {amount} → {tax}")
    return breakdown


def render_html(record: ShareRecord) -> str:
    translator = get_translator(record.locale)
    payload = record.payload
    summary = payload.get("summary", {}) if isinstance(payload, Mapping) else {}
    details = payload.get("details", []) if isinstance(payload, Mapping) else []

    summary_rows_html = "\n".join(
        f"<tr><th>{label}</th><td>{value}</td></tr>" for label, value in _summary_rows(summary, translator)
    )

    detail_cards: List[str] = []
    for detail in details:
        if not isinstance(detail, Mapping):
            continue
        label = detail.get("label") or detail.get("category") or ""
        rows_html = "\n".join(
            f"<tr><th>{row_label}</th><td>{row_value}</td></tr>"
            for row_label, row_value in _detail_rows(detail, translator)
        )
        breakdown_items = _detail_breakdown(detail, translator)
        breakdown_html = ""
        if breakdown_items:
            breakdown_html = (
                f"<section class=\"breakdown\"><h4>{translator('share.detail_fields.breakdown')}</h4>"
                f"<ul>{''.join(f'<li>{item}</li>' for item in breakdown_items)}</ul></section>"
            )
        detail_cards.append(
            f"<article class=\"detail-card\"><h3>{label}</h3><table>{rows_html}</table>{breakdown_html}</article>"
        )

    generated_with = translator("share.generated_with")

    return f"""<!DOCTYPE html>
<html lang=\"{record.locale}\">
  <head>
    <meta charset=\"utf-8\" />
    <title>{translator('share.title')}</title>
    <style>
      body {{ font-family: 'Segoe UI', sans-serif; margin: 0; padding: 2rem; color: #212529; background: #f8f9fa; }}
      h1, h2, h3, h4 {{ margin-top: 0; }}
      header {{ margin-bottom: 1.5rem; }}
      table {{ width: 100%; border-collapse: collapse; margin-bottom: 1rem; }}
      th, td {{ padding: 0.5rem; text-align: left; border-bottom: 1px solid #dee2e6; }}
      .summary-table th {{ width: 50%; }}
      .detail-card {{ background: #fff; border: 1px solid #dee2e6; border-radius: 0.5rem; padding: 1rem; margin-bottom: 1rem; }}
      .detail-card table {{ margin-bottom: 0; }}
      .breakdown ul {{ margin: 0.5rem 0 0 1.25rem; }}
      footer {{ margin-top: 2rem; font-size: 0.9rem; color: #6c757d; }}
    </style>
  </head>
  <body>
    <header>
      <h1>{translator('share.heading')}</h1>
    </header>
    <section>
      <h2>{translator('share.summary_heading')}</h2>
      <table class=\"summary-table\">
        <tbody>
          {summary_rows_html}
        </tbody>
      </table>
    </section>
    <section>
      <h2>{translator('share.detail_heading')}</h2>
      {''.join(detail_cards)}
    </section>
    <footer>
      <p>{generated_with}</p>
    </footer>
  </body>
</html>"""


def render_csv(record: ShareRecord) -> str:
    translator = get_translator(record.locale)
    payload = record.payload
    summary = payload.get("summary", {}) if isinstance(payload, Mapping) else {}
    details = payload.get("details", []) if isinstance(payload, Mapping) else []

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow([translator("share.summary_heading"), translator("share.detail_fields.breakdown"), translator("share.detail_fields.net_income")])
    for label, value in _summary_rows(summary, translator):
        writer.writerow([translator("share.summary_heading"), label, value])

    writer.writerow([])
    for detail in details:
        if not isinstance(detail, Mapping):
            continue
        section_label = detail.get("label") or detail.get("category") or ""
        for row_label, row_value in _detail_rows(detail, translator):
            writer.writerow([section_label, row_label, row_value])
        breakdown_items = _detail_breakdown(detail, translator)
        if breakdown_items:
            writer.writerow([section_label, translator("share.detail_fields.breakdown"), "; ".join(breakdown_items)])

    return buffer.getvalue()


def render_pdf(record: ShareRecord) -> bytes:
    translator = get_translator(record.locale)
    payload = record.payload
    summary = payload.get("summary", {}) if isinstance(payload, Mapping) else {}
    details = payload.get("details", []) if isinstance(payload, Mapping) else []

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    font_path = ensure_noto_sans()
    if font_path and font_path.exists():  # pragma: no branch - deterministic in tests
        pdf.add_font("NotoSans", fname=str(font_path))
        heading_family = body_family = "NotoSans"
        heading_style = ""
    else:  # pragma: no cover - executed when font extraction fails
        heading_family = "Helvetica"
        body_family = "Helvetica"
        heading_style = "B"

    pdf.set_title(translator("share.title"))
    pdf.set_text_color(33, 37, 41)
    pdf.set_draw_color(222, 226, 230)

    pdf.set_font(heading_family, style=heading_style, size=16)
    pdf.cell(0, 10, translator("share.heading"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font(body_family, size=12)
    pdf.ln(2)
    pdf.set_font(body_family, size=12)
    pdf.set_fill_color(248, 249, 250)
    pdf.cell(0, 8, translator("share.summary_heading"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    for label, value in _summary_rows(summary, translator):
        pdf.multi_cell(pdf.epw, 6, f"{label}: {value}")

    pdf.ln(4)
    pdf.cell(0, 8, translator("share.detail_heading"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    for detail in details:
        if not isinstance(detail, Mapping):
            continue
        pdf.ln(2)
        label = detail.get("label") or detail.get("category") or ""
        pdf.set_font(body_family, size=12)
        pdf.multi_cell(pdf.epw, 7, label)
        for row_label, row_value in _detail_rows(detail, translator):
            pdf.multi_cell(pdf.epw, 6, f"{row_label}: {row_value}")
        breakdown_items = _detail_breakdown(detail, translator)
        if breakdown_items:
            pdf.multi_cell(
                pdf.epw,
                6,
                f"{translator('share.detail_fields.breakdown')}: {', '.join(breakdown_items)}",
            )

    pdf.ln(6)
    pdf.multi_cell(0, 6, translator("share.generated_with"))

    output = pdf.output()
    if isinstance(output, (bytes, bytearray)):
        return bytes(output)
    return output.encode("latin1")


__all__ = [
    "InMemoryShareRepository",
    "SQLiteShareRepository",
    "ExpiryFeedbackCollector",
    "ShareRecord",
    "render_html",
    "render_csv",
    "render_pdf",
]
