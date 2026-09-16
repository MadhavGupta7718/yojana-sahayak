"""Helpers to collapse title-variant duplicate schemes in listings."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import Scheme
from scraper.change_detection.promote import _normalize_entity_key


def _ts(value: datetime | None) -> datetime:
    if value is None:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def dedupe_schemes(schemes: Iterable[Scheme]) -> list[Scheme]:
    """
    Keep one row per (source_id, normalized canonical key).

    When a publisher renames a scheme (e.g. inserts Men/Women), crawls can leave
    both the old and new rows active. Explore/Find should show only the newest.
    """
    best: dict[tuple[int, str], Scheme] = {}
    for s in schemes:
        source = int(s.source_id or 0)
        norm = _normalize_entity_key(s.canonical_key) or f"id-{s.id}"
        key = (source, norm)
        prev = best.get(key)
        if prev is None:
            best[key] = s
            continue
        if _ts(s.last_verified) > _ts(prev.last_verified) or (
            _ts(s.last_verified) == _ts(prev.last_verified) and (s.id or 0) > (prev.id or 0)
        ):
            best[key] = s
    return sorted(best.values(), key=lambda x: (x.name or "").lower())


def active_scheme_rows(db: Session) -> list[Scheme]:
    return (
        db.query(Scheme)
        .filter(Scheme.status.in_(["active", "unavailable"]))
        .order_by(Scheme.name)
        .all()
    )


def active_unique_schemes(db: Session) -> list[Scheme]:
    return dedupe_schemes(active_scheme_rows(db))


def count_active_unique(db: Session) -> int:
    return len(active_unique_schemes(db))


def retire_stale_duplicates(db: Session) -> list[int]:
    """
    Mark older title-variant duplicates as discontinued so Admin/Explore/Find agree.
    Keeps the newest row per (source_id, normalized key).
    """
    active = active_scheme_rows(db)
    keep_ids = {s.id for s in dedupe_schemes(active)}
    retired: list[int] = []
    for s in active:
        if s.id in keep_ids:
            continue
        s.status = "discontinued"
        retired.append(s.id)
    return retired
