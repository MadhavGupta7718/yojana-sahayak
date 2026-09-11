"""Compare staging payloads with production and create data_changes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import (
    ApprovalRule,
    DataChange,
    Partner,
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


def _is_sensitive(db: Session, field_name: str) -> tuple[bool, bool]:
    rule = db.query(ApprovalRule).filter(ApprovalRule.field_name == field_name).first()
    if rule:
        return rule.is_sensitive, rule.auto_approve
    return field_name in SENSITIVE_DEFAULT, field_name not in SENSITIVE_DEFAULT


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
        "source_url": scheme.source_url,
        "status": scheme.status,
    }


def promote_staging(db: Session, staging: StagingRecord) -> list[DataChange]:
    changes: list[DataChange] = []
    now = datetime.now(timezone.utc)
    payload = staging.payload or {}

    if staging.entity_type == "scheme":
        changes.extend(_promote_scheme(db, staging, payload, now))
    elif staging.entity_type == "partner":
        changes.extend(_promote_partner(db, staging, payload, now))

    staging.status = "compared"
    return changes


def _promote_scheme(db: Session, staging: StagingRecord, payload: dict, now: datetime) -> list[DataChange]:
    changes: list[DataChange] = []
    key = staging.entity_key or payload.get("canonical_key")
    scheme = db.query(Scheme).filter(Scheme.canonical_key == key).first()
    if not scheme:
        # New scheme — create with pending-sensitive review for financial fields
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
        # Apply non-sensitive + financial with change records
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
        ]:
            if field in payload and payload[field] is not None:
                sensitive, auto = _is_sensitive(db, field)
                if sensitive and not auto:
                    # Still set initial value from official source but flag for review
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
                        status="pending_review",
                        is_sensitive=True,
                    )
                    db.add(ch)
                    changes.append(ch)
                else:
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
                        is_sensitive=False,
                    )
                    db.add(ch)
                    changes.append(ch)

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

    # Existing scheme — differential update
    for field, new_val in payload.items():
        if field in {"name", "canonical_key", "source_url", "description"}:
            # description/name updates
            if field == "description" and new_val and new_val != scheme.description:
                sensitive, auto = _is_sensitive(db, field)
                status = "auto_approved" if auto or not sensitive else "pending_review"
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
                    status=status,
                    is_sensitive=sensitive,
                )
                db.add(ch)
                changes.append(ch)
                if status == "auto_approved":
                    scheme.description = new_val
            continue
        if not hasattr(scheme, field):
            continue
        old_val = getattr(scheme, field)
        if new_val is None:
            continue
        if _values_equal(old_val, new_val):
            continue
        sensitive, auto = _is_sensitive(db, field)
        # Conflict if another pending change exists with different new value
        pending = (
            db.query(DataChange)
            .filter(
                DataChange.entity_type == "scheme",
                DataChange.entity_id == scheme.id,
                DataChange.field_name == field,
                DataChange.status.in_(["pending_review", "detected"]),
            )
            .first()
        )
        is_conflict = bool(pending and not _values_equal(pending.new_value, new_val))
        status = "conflict" if is_conflict else ("auto_approved" if auto or not sensitive else "pending_review")
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
            status=status if not is_conflict else "pending_review",
            is_sensitive=sensitive,
            is_conflict=is_conflict,
            notes="Data conflict detected between official sources" if is_conflict else None,
        )
        db.add(ch)
        changes.append(ch)
        if status == "auto_approved":
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
        staging.status = "promoted"
        return changes

    for field in ["phone", "email", "address", "website", "state", "district", "status"]:
        if field in payload and payload[field] is not None and getattr(partner, field) != payload[field]:
            sensitive, auto = _is_sensitive(db, field)
            status = "auto_approved" if auto or not sensitive else "pending_review"
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
                status=status,
                is_sensitive=sensitive,
            )
            db.add(ch)
            changes.append(ch)
            if status == "auto_approved":
                setattr(partner, field, payload[field])
    partner.last_verified = now
    staging.status = "promoted"
    return changes


def apply_change(db: Session, change: DataChange, approve: bool, admin_id: int) -> None:
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
