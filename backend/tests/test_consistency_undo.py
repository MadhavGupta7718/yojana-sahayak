"""Regression: active-unique scheme counts, auto-apply promote, per-field undo."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.services.scheme_dedupe import dedupe_schemes, retire_stale_duplicates
from scraper.change_detection.promote import (
    UNDOABLE_STATUSES,
    _normalize_entity_key,
    _values_equal,
    undo_change,
)


def _scheme(**kwargs):
    defaults = {
        "id": 1,
        "name": "Beauty Parlour",
        "canonical_key": "beauty-parlour",
        "source_id": 1,
        "status": "active",
        "last_verified": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "interest_rate": 6.0,
        "interest_rate_type": None,
        "current_version": 1,
        "scheme_type": "loan",
        "purpose": "business",
        "description": "Desc",
        "min_income": None,
        "max_income": None,
        "min_loan": None,
        "max_loan": 100000,
        "tenure": None,
        "moratorium": None,
        "loan_percentage": None,
        "beneficiary_requirements": None,
        "eligible_activities": None,
        "required_documents": None,
        "application_process": None,
        "availability_type": None,
        "valid_from": None,
        "valid_to": None,
        "target_gender": "any",
        "source_url": "https://example.gov/scheme",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_resolve_run_id_from_staging_and_raw():
    from scraper.change_detection.promote import _resolve_run_id

    staging = SimpleNamespace(scraping_run_id=42, raw_document_id=None)
    assert _resolve_run_id(MagicMock(), staging) == 42

    staging2 = SimpleNamespace(scraping_run_id=None, raw_document_id=9)
    raw = SimpleNamespace(scraping_run_id=77)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = raw
    assert _resolve_run_id(db, staging2) == 77

    assert _normalize_entity_key("beauty-parlour-for-women") == "beauty-parlour"
    assert _normalize_entity_key("beauty-parlour-for-men") == "beauty-parlour"
    assert _normalize_entity_key("beauty-parlour-for-women") == _normalize_entity_key(
        "beauty-parlour-men"
    )


def test_dedupe_schemes_keeps_newest_title_variant():
    older = _scheme(
        id=10,
        name="Beauty Parlour",
        canonical_key="beauty-parlour",
        last_verified=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    newer = _scheme(
        id=20,
        name="Beauty Parlour for Men",
        canonical_key="beauty-parlour-for-men",
        last_verified=datetime(2025, 6, 1, tzinfo=timezone.utc),
    )
    kept = dedupe_schemes([older, newer])
    assert len(kept) == 1
    assert kept[0].id == 20


def test_retire_stale_duplicates_marks_older():
    older = _scheme(
        id=10,
        canonical_key="beauty-parlour",
        last_verified=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    newer = _scheme(
        id=20,
        canonical_key="beauty-parlour-for-men",
        last_verified=datetime(2025, 6, 1, tzinfo=timezone.utc),
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        older,
        newer,
    ]
    retired = retire_stale_duplicates(db)
    assert retired == [10]
    assert older.status == "discontinued"
    assert newer.status == "active"


def test_auto_apply_statuses_are_undoable():
    assert "auto_approved" in UNDOABLE_STATUSES
    assert "approved" in UNDOABLE_STATUSES
    assert "pending_review" not in UNDOABLE_STATUSES


def test_values_equal_tolerates_numeric_types():
    assert _values_equal(6, 6.0) is True
    assert _values_equal(6.5, 6.5) is True
    assert _values_equal(None, None) is True
    assert _values_equal(6, 7) is False


def test_undo_change_restores_single_field():
    scheme = _scheme(interest_rate=7.5, current_version=3)
    change = SimpleNamespace(
        id=50,
        status="auto_approved",
        field_name="interest_rate",
        old_value=6.0,
        new_value=7.5,
        entity_type="scheme",
        entity_id=1,
        source_id=1,
        source_url="https://example.gov/scheme",
        detected_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        notes=None,
        reviewed_by=None,
        reviewed_at=None,
    )

    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        name = getattr(model, "__name__", str(model))
        if "DataChange" in name or model is type(change):
            q.filter.return_value.first.return_value = None
        else:
            q.filter.return_value.first.return_value = scheme
        return q

    # undo_change queries DataChange for newer, then Scheme
    calls = {"n": 0}

    def query_fn(model):
        q = MagicMock()
        calls["n"] += 1
        if calls["n"] == 1:
            q.filter.return_value.first.return_value = None  # no newer change
        else:
            q.filter.return_value.first.return_value = scheme
        return q

    db.query.side_effect = query_fn

    undo_change(db, change, admin_id=9)

    assert scheme.interest_rate == 6.0
    assert scheme.current_version == 4
    assert change.status == "undone"
    assert change.reviewed_by == 9
    assert db.add.called


def test_undo_refuses_when_newer_field_change_exists():
    change = SimpleNamespace(
        id=50,
        status="auto_approved",
        field_name="interest_rate",
        old_value=6.0,
        new_value=7.5,
        entity_type="scheme",
        entity_id=1,
        notes=None,
    )
    newer = SimpleNamespace(id=51)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = newer
    try:
        undo_change(db, change, admin_id=1)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "newer change" in str(exc).lower()


def test_promote_scheme_update_always_auto_approved():
    """Existing-scheme field diffs must land as auto_approved (no pending_review)."""
    from scraper.change_detection.promote import _promote_scheme

    scheme = _scheme(interest_rate=6.0, description="Old", current_version=1)
    staging = SimpleNamespace(
        entity_key="beauty-parlour",
        source_id=1,
        source_url="https://example.gov/scheme",
        confidence=0.9,
        original_text="",
        status="pending",
    )
    payload = {
        "name": "Beauty Parlour",
        "canonical_key": "beauty-parlour",
        "interest_rate": 7.5,
        "description": "Updated terms",
    }

    db = MagicMock()

    def query_fn(model):
        q = MagicMock()
        q.filter.return_value.first.return_value = None
        q.filter.return_value.all.return_value = []
        q.filter.return_value.count.return_value = 1
        return q

    db.query.side_effect = query_fn

    import scraper.change_detection.promote as promote_mod

    original = promote_mod._find_existing_scheme
    promote_mod._find_existing_scheme = lambda *_a, **_k: scheme
    try:
        changes = _promote_scheme(db, staging, payload, datetime.now(timezone.utc))
    finally:
        promote_mod._find_existing_scheme = original

    assert scheme.interest_rate == 7.5
    assert scheme.description == "Updated terms"
    assert changes
    assert all(c.status == "auto_approved" for c in changes)
    assert any(c.field_name == "interest_rate" and c.old_value == 6.0 for c in changes)
