"""Compare staging payloads with production and create data_changes."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import (
    ApprovalRule,
    DataChange,
    Partner,
    PartnerSchemeMapping,
    RawDocument,
    Scheme,
    SchemeEligibilityRule,
    SchemeVersion,
    SourceCitation,
    StagingRecord,
)


SENSITIVE_DEFAULT = {
    "interest_rate",
    "max_loan",
    "min_loan",
    "max_income",
    "min_income",
    "tenure",
    "moratorium",
    "loan_percentage",
    "beneficiary_requirements",
    "eligible_activities",
    "npa_status",
    "overdue_status",
    "fund_utilization",
}

# Gender / filler tokens that often appear/disappear when publishers edit titles
_KEY_NOISE = re.compile(
    r"(?:^|-)(?:men|women|male|female|for-women|for-men)(?:-|$)",
    re.I,
)


def _normalize_entity_key(key: str | None) -> str:
    """Stable key for matching schemes after minor title edits (e.g. adding Men/Women)."""
    k = (key or "").strip().lower()
    if not k:
        return ""
    prev = None
    while prev != k:
        prev = k
        k = _KEY_NOISE.sub("-", k)
    k = re.sub(r"-+", "-", k).strip("-")
    return k


def _is_sensitive(db: Session, field_name: str) -> tuple[bool, bool]:
    rule = db.query(ApprovalRule).filter(ApprovalRule.field_name == field_name).first()
    if rule:
        return rule.is_sensitive, rule.auto_approve
    return field_name in SENSITIVE_DEFAULT, field_name not in SENSITIVE_DEFAULT


def _find_existing_scheme(db: Session, staging: StagingRecord, payload: dict) -> Optional[Scheme]:
    key = staging.entity_key or payload.get("canonical_key")
    scheme = db.query(Scheme).filter(Scheme.canonical_key == key).first()
    if scheme:
        return scheme

    # Title edits change canonical_key (e.g. insert "Men") — reuse same-source near match
    norm = _normalize_entity_key(key)
    if not norm or not staging.source_id:
        return None
    candidates = (
        db.query(Scheme)
        .filter(
            Scheme.source_id == staging.source_id,
            Scheme.status.in_(["active", "unavailable"]),
        )
        .all()
    )
    matches = [s for s in candidates if _normalize_entity_key(s.canonical_key) == norm]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        # Prefer exact-ish name containment / longest shared key
        name = str(payload.get("name") or "").lower()
        matches.sort(key=lambda s: (s.name or "").lower() in name or name in (s.name or "").lower(), reverse=True)
        return matches[0]
    return None


def _parse_iso_dt(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _scheme_snapshot(scheme: Scheme) -> dict[str, Any]:
    return {
        "name": scheme.name,
        "scheme_type": scheme.scheme_type,
        "purpose": scheme.purpose,
        "description": scheme.description,
        "min_income": scheme.min_income,
        "max_income": scheme.max_income,
        "min_loan": scheme.min_loan,
        "max_loan": scheme.max_loan,
        "interest_rate": scheme.interest_rate,
        "interest_rate_type": scheme.interest_rate_type,
        "tenure": scheme.tenure,
        "moratorium": scheme.moratorium,
        "loan_percentage": scheme.loan_percentage,
        "beneficiary_requirements": scheme.beneficiary_requirements,
        "eligible_activities": scheme.eligible_activities,
        "required_documents": scheme.required_documents,
        "application_process": scheme.application_process,
        "availability_type": getattr(scheme, "availability_type", None),
        "valid_from": scheme.valid_from.isoformat() if getattr(scheme, "valid_from", None) else None,
        "valid_to": scheme.valid_to.isoformat() if getattr(scheme, "valid_to", None) else None,
        "target_gender": getattr(scheme, "target_gender", None) or "any",
        "source_url": scheme.source_url,
        "status": scheme.status,
    }


from scraper.extractors.scheme_gate import is_loan_scheme_payload


def promote_staging(db: Session, staging: StagingRecord) -> list[DataChange]:
    changes: list[DataChange] = []
    now = datetime.now(timezone.utc)
    payload = staging.payload or {}

    if staging.entity_type == "scheme":
        # Final safety net: never insert/update Scheme rows for policy/FAQ/junk
        blob = " ".join(
            str(x)
            for x in (
                payload.get("description"),
                payload.get("name"),
                staging.original_text if isinstance(staging.original_text, str) else "",
            )
            if x
        )
        if not is_loan_scheme_payload(payload, url=staging.source_url or "", text=blob):
            staging.status = "rejected_non_scheme"
            return changes
        changes.extend(_promote_scheme(db, staging, payload, now))
    elif staging.entity_type == "partner":
        changes.extend(_promote_partner(db, staging, payload, now))

    run_id = _resolve_run_id(db, staging)
    if run_id:
        for ch in changes:
            if getattr(ch, "scraping_run_id", None) is None:
                ch.scraping_run_id = run_id
        if getattr(staging, "scraping_run_id", None) is None:
            staging.scraping_run_id = run_id

    staging.status = "compared"
    return changes


def _resolve_run_id(db: Session, staging: StagingRecord) -> Optional[int]:
    rid = getattr(staging, "scraping_run_id", None)
    if rid:
        return int(rid)
    if staging.raw_document_id:
        raw = db.query(RawDocument).filter(RawDocument.id == staging.raw_document_id).first()
        if raw and raw.scraping_run_id:
            return int(raw.scraping_run_id)
    return None


def _promote_scheme(db: Session, staging: StagingRecord, payload: dict, now: datetime) -> list[DataChange]:
    changes: list[DataChange] = []
    key = staging.entity_key or payload.get("canonical_key")
    scheme = _find_existing_scheme(db, staging, payload)
    if not scheme:
        # New scheme — apply all fields immediately; Change Review keeps an audit trail for Undo
        scheme = Scheme(
            name=payload.get("name") or "Unnamed scheme",
            canonical_key=key,
            scheme_type=payload.get("scheme_type"),
            purpose=payload.get("purpose"),
            description=payload.get("description"),
            source_id=staging.source_id,
            source_url=staging.source_url or payload.get("source_url"),
            last_verified=now,
            current_version=1,
            status="active",
            raw_fields=staging.original_text,
        )
        for field in [
            "min_income",
            "max_income",
            "min_loan",
            "max_loan",
            "interest_rate",
            "interest_rate_type",
            "tenure",
            "moratorium",
            "loan_percentage",
            "beneficiary_requirements",
            "eligible_activities",
            "required_documents",
            "application_process",
            "availability_type",
            "target_gender",
        ]:
            if field in payload and payload[field] is not None:
                sensitive, _auto = _is_sensitive(db, field)
                setattr(scheme, field, payload[field])
                ch = DataChange(
                    entity_type="scheme",
                    entity_key=key,
                    field_name=field,
                    old_value=None,
                    new_value=payload[field],
                    source_id=staging.source_id,
                    source_url=staging.source_url,
                    detected_at=now,
                    confidence=staging.confidence,
                    status="auto_approved",
                    is_sensitive=sensitive,
                    notes="Applied on ingest; undo restores previous value when available",
                )
                db.add(ch)
                changes.append(ch)

        if "valid_from" in payload:
            scheme.valid_from = _parse_iso_dt(payload.get("valid_from"))
        if "valid_to" in payload:
            scheme.valid_to = _parse_iso_dt(payload.get("valid_to"))
        if payload.get("target_gender"):
            scheme.target_gender = payload["target_gender"]
        elif not scheme.target_gender:
            scheme.target_gender = "any"

        db.add(scheme)
        db.flush()
        db.add(
            SchemeVersion(
                scheme_id=scheme.id,
                version_number=1,
                data_snapshot=_scheme_snapshot(scheme),
                effective_from=now,
                source_id=staging.source_id,
                source_url=scheme.source_url,
                retrieved_at=now,
                verified_at=now,
                status="active",
            )
        )
        _upsert_citations(db, scheme, staging, payload, now)
        _ensure_rules(db, scheme, staging.source_id)
        for ch in changes:
            ch.entity_id = scheme.id
        staging.status = "promoted"
        return changes

    # Existing scheme — differential update (always auto-apply; log for Undo in Change Review)
    # Keep title/key in sync when publisher renames slightly (Men/Women inserted, etc.)
    new_name = payload.get("name")
    if new_name and new_name != scheme.name:
        ch = DataChange(
            entity_type="scheme",
            entity_id=scheme.id,
            entity_key=key,
            field_name="name",
            old_value=scheme.name,
            new_value=new_name,
            source_id=staging.source_id,
            source_url=staging.source_url,
            detected_at=now,
            confidence=staging.confidence,
            status="auto_approved",
            is_sensitive=False,
        )
        db.add(ch)
        changes.append(ch)
        scheme.name = new_name
    if key and key != scheme.canonical_key:
        # Avoid unique collisions if another row already owns the new key
        clash = db.query(Scheme).filter(Scheme.canonical_key == key, Scheme.id != scheme.id).first()
        if clash and clash.source_id == scheme.source_id:
            clash.status = "discontinued"
        if not clash or clash.source_id == scheme.source_id:
            old_key = scheme.canonical_key
            scheme.canonical_key = key
            ch = DataChange(
                entity_type="scheme",
                entity_id=scheme.id,
                entity_key=key,
                field_name="canonical_key",
                old_value=old_key,
                new_value=key,
                source_id=staging.source_id,
                source_url=staging.source_url,
                detected_at=now,
                confidence=staging.confidence,
                status="auto_approved",
                is_sensitive=False,
            )
            db.add(ch)
            changes.append(ch)

    for field, new_val in payload.items():
        if field in {"name", "canonical_key", "source_url"}:
            if field == "source_url" and new_val and new_val != scheme.source_url:
                scheme.source_url = new_val
            continue
        if field == "description":
            if new_val and new_val != scheme.description:
                sensitive, _auto = _is_sensitive(db, field)
                ch = DataChange(
                    entity_type="scheme",
                    entity_id=scheme.id,
                    entity_key=key,
                    field_name=field,
                    old_value=scheme.description,
                    new_value=new_val,
                    source_id=staging.source_id,
                    source_url=staging.source_url,
                    detected_at=now,
                    confidence=staging.confidence,
                    status="auto_approved",
                    is_sensitive=sensitive,
                )
                db.add(ch)
                changes.append(ch)
                scheme.description = new_val
            continue
        if field in {"valid_from", "valid_to"}:
            new_val = _parse_iso_dt(new_val)
        if not hasattr(scheme, field):
            continue
        old_val = getattr(scheme, field)
        if new_val is None and field not in {"valid_from", "valid_to", "availability_type"}:
            continue
        if _values_equal(old_val, new_val):
            continue
        sensitive, _auto = _is_sensitive(db, field)
        # Close any leftover pending rows for this field (legacy queue)
        pending_rows = (
            db.query(DataChange)
            .filter(
                DataChange.entity_type == "scheme",
                DataChange.entity_id == scheme.id,
                DataChange.field_name == field,
                DataChange.status.in_(["pending_review", "detected", "conflict"]),
            )
            .all()
        )
        for pending in pending_rows:
            pending.status = "superseded"
            pending.notes = ((pending.notes or "") + " | superseded by auto-applied crawl").strip(" |")
        ch = DataChange(
            entity_type="scheme",
            entity_id=scheme.id,
            entity_key=key,
            field_name=field,
            old_value=old_val,
            new_value=new_val,
            source_id=staging.source_id,
            source_url=staging.source_url,
            detected_at=now,
            confidence=staging.confidence,
            status="auto_approved",
            is_sensitive=sensitive,
            is_conflict=False,
        )
        db.add(ch)
        changes.append(ch)
        setattr(scheme, field, new_val)

    if changes:
        # New version snapshot of current production state after auto applies
        scheme.current_version = (scheme.current_version or 1) + 1
        scheme.last_verified = now
        db.add(
            SchemeVersion(
                scheme_id=scheme.id,
                version_number=scheme.current_version,
                data_snapshot=_scheme_snapshot(scheme),
                effective_from=now,
                source_id=staging.source_id,
                source_url=staging.source_url or scheme.source_url,
                retrieved_at=now,
                verified_at=now,
                status="active",
            )
        )
        _upsert_citations(db, scheme, staging, payload, now)
        _ensure_rules(db, scheme, staging.source_id)
        # Drop older title-variant duplicates from the same source
        norm = _normalize_entity_key(scheme.canonical_key)
        if norm and scheme.source_id:
            for other in (
                db.query(Scheme)
                .filter(
                    Scheme.source_id == scheme.source_id,
                    Scheme.id != scheme.id,
                    Scheme.status.in_(["active", "unavailable"]),
                )
                .all()
            ):
                if _normalize_entity_key(other.canonical_key) == norm:
                    other.status = "discontinued"
    staging.status = "promoted"
    return changes


def _promote_partner(db: Session, staging: StagingRecord, payload: dict, now: datetime) -> list[DataChange]:
    changes: list[DataChange] = []
    key = staging.entity_key or payload.get("canonical_key")
    partner = db.query(Partner).filter(Partner.canonical_key == key).first()
    if not partner:
        partner = Partner(
            name=payload.get("name") or "Unnamed partner",
            canonical_key=key,
            partner_type=payload.get("partner_type"),
            organization=payload.get("organization"),
            state=payload.get("state"),
            district=payload.get("district"),
            address=payload.get("address"),
            latitude=payload.get("latitude"),
            longitude=payload.get("longitude"),
            phone=payload.get("phone"),
            email=payload.get("email"),
            website=payload.get("website"),
            source_id=staging.source_id,
            source_url=staging.source_url or payload.get("source_url"),
            last_verified=now,
            status=payload.get("status") or "active",
        )
        db.add(partner)
        db.flush()
        ch = DataChange(
            entity_type="partner",
            entity_id=partner.id,
            entity_key=key,
            field_name="created",
            old_value=None,
            new_value=payload.get("name"),
            source_id=staging.source_id,
            source_url=staging.source_url,
            detected_at=now,
            status="auto_approved",
            is_sensitive=False,
        )
        db.add(ch)
        changes.append(ch)
        _link_partner_scheme(db, partner, payload)
        staging.status = "promoted"
        return changes

    for field in [
        "phone",
        "email",
        "address",
        "website",
        "state",
        "district",
        "status",
        "organization",
        "latitude",
        "longitude",
    ]:
        if field in payload and payload[field] is not None and getattr(partner, field) != payload[field]:
            sensitive, _auto = _is_sensitive(db, field)
            ch = DataChange(
                entity_type="partner",
                entity_id=partner.id,
                entity_key=key,
                field_name=field,
                old_value=getattr(partner, field),
                new_value=payload[field],
                source_id=staging.source_id,
                source_url=staging.source_url,
                detected_at=now,
                status="auto_approved",
                is_sensitive=sensitive,
            )
            db.add(ch)
            changes.append(ch)
            setattr(partner, field, payload[field])
    partner.last_verified = now
    _link_partner_scheme(db, partner, payload)
    staging.status = "promoted"
    return changes


def _link_partner_scheme(db: Session, partner: Partner, payload: dict) -> None:
    scheme_key = payload.get("linked_scheme_key")
    if not scheme_key:
        return
    scheme = db.query(Scheme).filter(Scheme.canonical_key == scheme_key).first()
    if not scheme:
        return
    existing = (
        db.query(PartnerSchemeMapping)
        .filter(
            PartnerSchemeMapping.partner_id == partner.id,
            PartnerSchemeMapping.scheme_id == scheme.id,
        )
        .first()
    )
    if existing:
        return
    db.add(
        PartnerSchemeMapping(
            partner_id=partner.id,
            scheme_id=scheme.id,
            eligibility_status="eligible",
            source_id=partner.source_id,
            last_verified=datetime.now(timezone.utc),
        )
    )


UNDOABLE_STATUSES = ("auto_approved", "approved", "applied")


def apply_change(db: Session, change: DataChange, approve: bool, admin_id: int) -> None:
    """Legacy approve/reject for leftover pending rows; new crawls auto-apply instead."""
    change.reviewed_by = admin_id
    change.reviewed_at = datetime.now(timezone.utc)
    if not approve:
        change.status = "rejected"
        return
    change.status = "approved"
    if change.entity_type == "scheme" and change.entity_id:
        scheme = db.query(Scheme).filter(Scheme.id == change.entity_id).first()
        if scheme and hasattr(scheme, change.field_name):
            setattr(scheme, change.field_name, change.new_value)
            scheme.last_verified = change.reviewed_at
            scheme.current_version = (scheme.current_version or 1) + 1
            db.add(
                SchemeVersion(
                    scheme_id=scheme.id,
                    version_number=scheme.current_version,
                    data_snapshot=_scheme_snapshot(scheme),
                    effective_from=change.reviewed_at,
                    source_id=change.source_id,
                    source_url=change.source_url,
                    retrieved_at=change.detected_at,
                    verified_at=change.reviewed_at,
                    status="active",
                )
            )
    elif change.entity_type == "partner" and change.entity_id:
        partner = db.query(Partner).filter(Partner.id == change.entity_id).first()
        if partner and hasattr(partner, change.field_name):
            setattr(partner, change.field_name, change.new_value)
            partner.last_verified = change.reviewed_at


def undo_change(db: Session, change: DataChange, admin_id: int) -> None:
    """Per-field undo: restore old_value on the live entity and mark the change undone."""
    if change.status not in UNDOABLE_STATUSES:
        raise ValueError("Change is not undoable")
    if change.field_name == "created":
        raise ValueError("Cannot undo entity creation via field undo")

    # Prefer undoing newest first when multiple applied edits exist for the same field
    newer = (
        db.query(DataChange)
        .filter(
            DataChange.entity_type == change.entity_type,
            DataChange.entity_id == change.entity_id,
            DataChange.field_name == change.field_name,
            DataChange.status.in_(list(UNDOABLE_STATUSES)),
            DataChange.id > change.id,
        )
        .first()
    )
    if newer:
        raise ValueError("A newer change was applied for this field; undo that first")

    now = datetime.now(timezone.utc)
    change.reviewed_by = admin_id
    change.reviewed_at = now

    if change.entity_type == "scheme" and change.entity_id:
        scheme = db.query(Scheme).filter(Scheme.id == change.entity_id).first()
        if not scheme:
            raise ValueError("Scheme not found")
        if not hasattr(scheme, change.field_name):
            raise ValueError(f"Unknown field: {change.field_name}")
        current = getattr(scheme, change.field_name)
        if not _values_equal(current, change.new_value) and change.new_value is not None:
            # Live value diverged (manual edit or later path) — still restore old_value
            pass
        setattr(scheme, change.field_name, change.old_value)
        scheme.last_verified = now
        scheme.current_version = (scheme.current_version or 1) + 1
        db.add(
            SchemeVersion(
                scheme_id=scheme.id,
                version_number=scheme.current_version,
                data_snapshot=_scheme_snapshot(scheme),
                effective_from=now,
                source_id=change.source_id,
                source_url=change.source_url,
                retrieved_at=change.detected_at,
                verified_at=now,
                status="active",
            )
        )
    elif change.entity_type == "partner" and change.entity_id:
        partner = db.query(Partner).filter(Partner.id == change.entity_id).first()
        if not partner:
            raise ValueError("Partner not found")
        if not hasattr(partner, change.field_name):
            raise ValueError(f"Unknown field: {change.field_name}")
        setattr(partner, change.field_name, change.old_value)
        partner.last_verified = now
    else:
        raise ValueError("Change has no target entity")

    change.status = "undone"
    change.notes = ((change.notes or "") + " | undone by admin").strip(" |")


def flush_pending_changes(db: Session, admin_id: int = 0) -> list[int]:
    """Apply any leftover pending_review rows so Change Review is undo-only."""
    pending = (
        db.query(DataChange)
        .filter(DataChange.status.in_(["pending_review", "detected", "conflict"]))
        .order_by(DataChange.id.asc())
        .all()
    )
    applied: list[int] = []
    for change in pending:
        apply_change(db, change, True, admin_id)
        change.status = "auto_approved"
        applied.append(change.id)
    return applied


def _values_equal(a: Any, b: Any) -> bool:
    if a is None and b is None:
        return True
    if type(a) != type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        return str(a) == str(b)
    return a == b


def _upsert_citations(db: Session, scheme: Scheme, staging: StagingRecord, payload: dict, now: datetime) -> None:
    url = staging.source_url or payload.get("source_url") or scheme.source_url
    if not url:
        return
    for field in ["max_loan", "interest_rate", "max_income", "tenure", "required_documents", "name"]:
        if payload.get(field) is None and field != "name":
            continue
        existing = (
            db.query(SourceCitation)
            .filter(
                SourceCitation.entity_type == "scheme",
                SourceCitation.entity_id == scheme.id,
                SourceCitation.field_name == field,
            )
            .first()
        )
        if existing:
            existing.source_url = url
            existing.source_id = staging.source_id
            existing.last_verified = now
            existing.retrieved_at = now
        else:
            db.add(
                SourceCitation(
                    entity_type="scheme",
                    entity_id=scheme.id,
                    field_name=field,
                    source_id=staging.source_id,
                    source_url=url,
                    source_title=payload.get("name"),
                    source_section=field,
                    retrieved_at=now,
                    last_verified=now,
                )
            )


def _ensure_rules(db: Session, scheme: Scheme, source_id: Optional[int]) -> None:
    existing = db.query(SchemeEligibilityRule).filter(SchemeEligibilityRule.scheme_id == scheme.id).count()
    if existing:
        return
    if scheme.max_income is not None:
        db.add(
            SchemeEligibilityRule(
                scheme_id=scheme.id,
                rule_type="income",
                operator="lte",
                value=scheme.max_income,
                description="Your family income is within the required limit.",
                source_id=source_id,
                is_hard=True,
            )
        )
    if scheme.max_loan is not None:
        db.add(
            SchemeEligibilityRule(
                scheme_id=scheme.id,
                rule_type="loan_amount",
                operator="lte",
                value=scheme.max_loan,
                description="Your requested loan is within the applicable limit.",
                source_id=source_id,
                is_hard=True,
            )
        )
    if scheme.beneficiary_requirements and isinstance(scheme.beneficiary_requirements, dict):
        cats = scheme.beneficiary_requirements.get("categories")
        if cats:
            db.add(
                SchemeEligibilityRule(
                    scheme_id=scheme.id,
                    rule_type="category",
                    operator="in",
                    value=cats,
                    description="Your category matches the published beneficiary requirement.",
                    source_id=source_id,
                    is_hard=True,
                )
            )
