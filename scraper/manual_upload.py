"""Ingest manually uploaded official documents into the same pipeline."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import GovernmentSource, RawDocument, ScrapingRun, StagingRecord
from scraper.change_detection.promote import promote_staging
from scraper.extractors.facts import extract_document_schemes, extract_partners
from scraper.extractors.normalize import canonical_key, content_hash
from scraper.extractors.scheme_gate import is_loan_scheme_payload
from scraper.parsers.content import extract_pdf_text, html_to_text


def ingest_upload(
    db: Session,
    source_id: int,
    filename: str,
    content: bytes,
    source_url: str | None = None,
) -> dict:
    source = db.query(GovernmentSource).filter(GovernmentSource.id == source_id).first()
    if not source:
        raise ValueError("Source not found")

    run = ScrapingRun(source_id=source.id, status="running", notes=f"manual upload: {filename}")
    db.add(run)
    db.flush()

    lower = filename.lower()
    if lower.endswith(".pdf"):
        text = extract_pdf_text(content)
        ctype = "pdf"
    else:
        text = html_to_text(content.decode("utf-8", errors="ignore"))
        ctype = "html"

    if not text or len(text.strip()) < 20:
        run.status = "failed"
        run.error_count = 1
        run.end_time = datetime.now(timezone.utc)
        db.commit()
        raise ValueError("Could not extract text from uploaded document")

    url = source_url or f"manual://{source.source_name}/{filename}"
    digest = content_hash(text)
    raw = RawDocument(
        source_id=source.id,
        url=url,
        title=filename,
        content_type=ctype,
        content_hash=digest,
        raw_text=text[:200000],
        scraping_run_id=run.id,
        metadata_json={"upload": True, "filename": filename},
    )
    db.add(raw)
    db.flush()

    changes_count = 0
    schemes = extract_document_schemes(text, filename, url)
    if not schemes:
        from scraper.extractors.facts import extract_scheme_fields

        schemes = [extract_scheme_fields(text, filename, url)]

    for scheme_data in schemes:
        payload = scheme_data["payload"]
        if not is_loan_scheme_payload(payload, url=url, text=text):
            continue
        staging = StagingRecord(
            source_id=source.id,
            raw_document_id=raw.id,
            entity_type="scheme",
            entity_key=payload.get("canonical_key") or canonical_key(payload.get("name") or filename),
            payload=payload,
            original_text=scheme_data.get("original_text"),
            confidence=0.7,
            status="pending",
            source_url=url,
        )
        db.add(staging)
        db.flush()
        changes = promote_staging(db, staging)
        changes_count += len(changes)

        for partner in scheme_data.get("partners") or []:
            st = StagingRecord(
                source_id=source.id,
                raw_document_id=raw.id,
                entity_type="partner",
                entity_key=partner["canonical_key"],
                payload=partner,
                confidence=0.75,
                status="pending",
                source_url=url,
            )
            db.add(st)
            db.flush()
            changes_count += len(promote_staging(db, st))

    # Fallback partner pass for documents that only list partners
    if not any(s.get("partners") for s in schemes):
        for partner in extract_partners(text, url):
            st = StagingRecord(
                source_id=source.id,
                raw_document_id=raw.id,
                entity_type="partner",
                entity_key=partner["canonical_key"],
                payload=partner,
                confidence=0.5,
                status="pending",
                source_url=url,
            )
            db.add(st)
            db.flush()
            changes_count += len(promote_staging(db, st))

    run.documents_processed = 1
    run.changes_detected = changes_count
    run.status = "success"
    run.end_time = datetime.now(timezone.utc)
    source.last_successful_crawl = datetime.now(timezone.utc)
    db.commit()
    return {"raw_document_id": raw.id, "changes": changes_count, "schemes": len(schemes)}
