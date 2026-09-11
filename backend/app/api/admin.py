from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import (
    AdminUser,
    DataChange,
    GovernmentSource,
    Partner,
    Scheme,
    SchemeVersion,
    ScrapingError,
    ScrapingRun,
)
from app.schemas import ChangeDecision, SourceCreate, SourceUpdate
from app.services.auth import (
    authenticate_admin,
    create_access_token,
    get_current_admin,
    require_roles,
    write_audit,
)
from scraper.manual_upload import ingest_upload
from scraper.spiders.http_crawler import SourceCrawler

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_admin(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token({"sub": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "role": user.role, "username": user.username}


@router.get("/me")
def me(admin: AdminUser = Depends(get_current_admin)):
    return {"id": admin.id, "username": admin.username, "role": admin.role}


@router.get("/overview")
def overview(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    return {
        "total_schemes": db.query(Scheme).count(),
        "total_partners": db.query(Partner).count(),
        "government_sources": db.query(GovernmentSource).count(),
        "enabled_sources": db.query(GovernmentSource).filter(GovernmentSource.enabled.is_(True)).count(),
        "successful_runs": db.query(ScrapingRun).filter(ScrapingRun.status == "success").count(),
        "failed_runs": db.query(ScrapingRun).filter(ScrapingRun.status.in_(["failed", "ERROR"])).count(),
        "pending_changes": db.query(DataChange)
        .filter(DataChange.status.in_(["pending_review", "detected"]))
        .count(),
        "stale_schemes": db.query(Scheme).filter(Scheme.last_verified.is_(None)).count(),
    }


@router.get("/sources")
def list_sources(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    sources = db.query(GovernmentSource).order_by(GovernmentSource.id).all()
    return [
        {
            "id": s.id,
            "source_name": s.source_name,
            "organization": s.organization,
            "base_url": s.base_url,
            "source_type": s.source_type,
            "authority_level": s.authority_level,
            "enabled": s.enabled,
            "crawl_frequency": s.crawl_frequency,
            "robots_allowed": s.robots_allowed,
            "last_checked": s.last_checked,
            "last_successful_crawl": s.last_successful_crawl,
            "last_changed": s.last_changed,
            "status": s.status,
            "notes": s.notes,
            "discovery_status": s.discovery_status,
        }
        for s in sources
    ]


@router.post("/sources")
def create_source(
    body: SourceCreate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_roles("superadmin", "reviewer")),
):
    if db.query(GovernmentSource).filter(GovernmentSource.source_name == body.source_name).first():
        raise HTTPException(400, "Source name already exists")
    src = GovernmentSource(**body.model_dump(), status="PENDING", discovery_status="approved")
    db.add(src)
    write_audit(db, admin, "create_source", "government_source", details=body.model_dump())
    db.commit()
    db.refresh(src)
    return {"id": src.id}


@router.patch("/sources/{source_id}")
def update_source(
    source_id: int,
    body: SourceUpdate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_roles("superadmin", "reviewer")),
):
    src = db.query(GovernmentSource).filter(GovernmentSource.id == source_id).first()
    if not src:
        raise HTTPException(404, "Source not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(src, k, v)
    write_audit(db, admin, "update_source", "government_source", source_id, body.model_dump(exclude_unset=True))
    db.commit()
    return {"ok": True}


@router.post("/sources/{source_id}/crawl")
def trigger_crawl(
    source_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_roles("superadmin", "reviewer")),
):
    src = db.query(GovernmentSource).filter(GovernmentSource.id == source_id).first()
    if not src:
        raise HTTPException(404, "Source not found")
    if not src.enabled:
        raise HTTPException(400, "Source is disabled")
    run = SourceCrawler(db, src).crawl()
    write_audit(db, admin, "trigger_crawl", "government_source", source_id, {"run_id": run.id})
    return {
        "run_id": run.id,
        "status": run.status,
        "pages_crawled": run.pages_crawled,
        "documents_processed": run.documents_processed,
        "changes_detected": run.changes_detected,
        "error_count": run.error_count,
    }


@router.get("/changes")
def list_changes(
    status: str | None = None,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    q = db.query(DataChange).order_by(DataChange.detected_at.desc())
    if status:
        q = q.filter(DataChange.status == status)
    rows = q.limit(200).all()
    return [
        {
            "id": c.id,
            "entity_type": c.entity_type,
            "entity_id": c.entity_id,
            "entity_key": c.entity_key,
            "field_name": c.field_name,
            "old_value": c.old_value,
            "new_value": c.new_value,
            "source_id": c.source_id,
            "source_url": c.source_url,
            "detected_at": c.detected_at,
            "status": c.status,
            "is_sensitive": c.is_sensitive,
            "is_conflict": c.is_conflict,
            "notes": c.notes,
        }
        for c in rows
    ]


@router.post("/changes/{change_id}/decide")
def decide_change(
    change_id: int,
    body: ChangeDecision,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_roles("superadmin", "reviewer")),
):
    from scraper.change_detection.promote import apply_change

    change = db.query(DataChange).filter(DataChange.id == change_id).first()
    if not change:
        raise HTTPException(404, "Change not found")
    apply_change(db, change, body.approve, admin.id)
    if body.notes:
        change.notes = body.notes
    write_audit(
        db,
        admin,
        "approve_change" if body.approve else "reject_change",
        "data_change",
        change_id,
        {"approve": body.approve},
    )
    db.commit()
    return {"ok": True, "status": change.status}


@router.get("/runs")
def list_runs(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    runs = db.query(ScrapingRun).order_by(ScrapingRun.start_time.desc()).limit(100).all()
    return [
        {
            "id": r.id,
            "source_id": r.source_id,
            "start_time": r.start_time,
            "end_time": r.end_time,
            "status": r.status,
            "pages_crawled": r.pages_crawled,
            "documents_processed": r.documents_processed,
            "changes_detected": r.changes_detected,
            "error_count": r.error_count,
            "notes": r.notes,
        }
        for r in runs
    ]


@router.get("/errors")
def list_errors(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    errs = db.query(ScrapingError).order_by(ScrapingError.created_at.desc()).limit(100).all()
    return [
        {
            "id": e.id,
            "scraping_run_id": e.scraping_run_id,
            "source_id": e.source_id,
            "url": e.url,
            "error_type": e.error_type,
            "message": e.message,
            "created_at": e.created_at,
        }
        for e in errs
    ]


@router.get("/schemes")
def admin_schemes(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    schemes = db.query(Scheme).order_by(Scheme.id).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "status": s.status,
            "current_version": s.current_version,
            "last_verified": s.last_verified,
            "source_url": s.source_url,
            "interest_rate": s.interest_rate,
            "max_loan": s.max_loan,
            "max_income": s.max_income,
        }
        for s in schemes
    ]


@router.get("/schemes/{scheme_id}/versions")
def scheme_versions(
    scheme_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)
):
    versions = (
        db.query(SchemeVersion)
        .filter(SchemeVersion.scheme_id == scheme_id)
        .order_by(SchemeVersion.version_number.desc())
        .all()
    )
    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "data_snapshot": v.data_snapshot,
            "effective_from": v.effective_from,
            "effective_to": v.effective_to,
            "source_url": v.source_url,
            "retrieved_at": v.retrieved_at,
            "verified_at": v.verified_at,
            "status": v.status,
        }
        for v in versions
    ]


@router.get("/partners")
def admin_partners(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    partners = db.query(Partner).order_by(Partner.id).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "state": p.state,
            "district": p.district,
            "status": p.status,
            "last_verified": p.last_verified,
            "source_url": p.source_url,
            "latitude": p.latitude,
            "longitude": p.longitude,
        }
        for p in partners
    ]


@router.post("/uploads")
async def upload_document(
    source_id: int = Form(...),
    source_url: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_roles("superadmin", "reviewer")),
):
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "File too large")
    try:
        result = ingest_upload(db, source_id, file.filename or "upload.bin", content, source_url)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    write_audit(db, admin, "manual_upload", "raw_document", result.get("raw_document_id"), result)
    db.commit()
    return result
