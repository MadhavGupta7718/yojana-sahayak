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
from scraper.validators.crawlability import probe_crawlability
from app.config import get_settings

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


@router.post("/sources/{source_id}/crawl-check")
def crawl_check(
    source_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_roles("superadmin", "reviewer")),
):
    """Probe robots.txt + homepage before a full crawl."""
    from datetime import datetime, timezone

    src = db.query(GovernmentSource).filter(GovernmentSource.id == source_id).first()
    if not src:
        raise HTTPException(404, "Source not found")
    settings = get_settings()
    result = probe_crawlability(src.base_url, settings.crawler_user_agent)
    src.robots_allowed = result["robots_allowed"]
    src.last_checked = datetime.now(timezone.utc)
    # Keep prior notes; append check summary lightly
    note = f"crawl-check: {result['verdict']} — {result['robots_notes']}"
    if src.notes and note not in src.notes:
        src.notes = f"{src.notes} | {note}"
    elif not src.notes:
        src.notes = note
    if result["verdict"] == "blocked":
        src.status = "MANUAL/RESTRICTED"
    elif result["verdict"] == "allowed":
        src.status = "ACTIVE"
    else:
        src.status = "WARNING"
    write_audit(db, admin, "crawl_check", "government_source", source_id, {"verdict": result["verdict"]})
    db.commit()
    return {
        "source_id": source_id,
        "source_name": src.source_name,
        "base_url": src.base_url,
        "crawlability": result,
    }


@router.post("/sources/{source_id}/crawl")
def trigger_crawl(
    source_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_roles("superadmin", "reviewer")),
):
    """Probe crawlability, create a queued ScrapingRun, then push work to the scraper."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import and_, or_

    from app.config import get_settings

    # Only auto-close truly abandoned runs (PDF-heavy crawls often exceed 12 minutes).
    now = datetime.now(timezone.utc)
    stale_running_cutoff = now - timedelta(minutes=90)
    stale_queued_cutoff = now - timedelta(minutes=30)
    stale_runs = (
        db.query(ScrapingRun)
        .filter(
            ScrapingRun.end_time.is_(None),
            or_(
                and_(ScrapingRun.status == "running", ScrapingRun.start_time < stale_running_cutoff),
                and_(ScrapingRun.status == "queued", ScrapingRun.start_time < stale_queued_cutoff),
            ),
        )
        .all()
    )
    for run in stale_runs:
        run.status = "failed"
        run.end_time = now
        run.notes = ((run.notes or "") + " | auto-closed stale crawl").strip(" |")
    if stale_runs:
        db.commit()

    src = db.query(GovernmentSource).filter(GovernmentSource.id == source_id).first()
    if not src:
        raise HTTPException(404, "Source not found")
    if not src.enabled:
        raise HTTPException(400, "Source is disabled. Enable it after review, then crawl.")

    active = (
        db.query(ScrapingRun)
        .filter(
            ScrapingRun.source_id == source_id,
            ScrapingRun.status.in_(("queued", "running")),
            ScrapingRun.end_time.is_(None),
        )
        .order_by(ScrapingRun.id.desc())
        .first()
    )
    if active:
        return {
            "run_id": active.id,
            "status": active.status,
            "started": False,
            "message": f"Crawl already {active.status} for this source (run #{active.id}).",
            "crawlability": None,
        }

    other = (
        db.query(ScrapingRun)
        .filter(
            ScrapingRun.status.in_(("queued", "running")),
            ScrapingRun.end_time.is_(None),
        )
        .order_by(ScrapingRun.id.desc())
        .first()
    )
    if other:
        return {
            "run_id": other.id,
            "status": other.status,
            "started": False,
            "message": (
                f"Another crawl is already {other.status} (run #{other.id}, source {other.source_id}). "
                "Wait for it to finish, or use Clear stuck crawls if it is frozen."
            ),
            "crawlability": None,
        }

    settings = get_settings()
    crawlability = probe_crawlability(src.base_url, settings.crawler_user_agent)
    src.robots_allowed = crawlability["robots_allowed"]
    src.last_checked = now
    if crawlability["verdict"] == "blocked":
        src.status = "MANUAL/RESTRICTED"
        write_audit(
            db,
            admin,
            "trigger_crawl_blocked",
            "government_source",
            source_id,
            {"crawlability": crawlability},
        )
        db.commit()
        return {
            "status": "blocked",
            "started": False,
            "source_id": source_id,
            "message": crawlability["summary"],
            "crawlability": crawlability,
        }
    if crawlability["verdict"] == "allowed":
        src.status = "ACTIVE"
    else:
        src.status = "WARNING"

    run = ScrapingRun(
        source_id=source_id,
        status="queued",
        notes="queued by admin for scraper worker",
    )
    db.add(run)
    write_audit(
        db,
        admin,
        "trigger_crawl",
        "government_source",
        source_id,
        {"queued": True, "crawlability": crawlability},
    )
    db.commit()
    db.refresh(run)

    try:
        import redis

        r = redis.from_url(settings.redis_url, decode_responses=True)
        r.lpush("yojana:crawl_now", f"{source_id}:{run.id}")
        r.close()
    except Exception as exc:
        run.status = "failed"
        run.end_time = datetime.now(timezone.utc)
        run.notes = ((run.notes or "") + f" | queue failed: {exc}").strip(" |")
        db.commit()
        raise HTTPException(500, f"Could not queue crawl for scraper worker: {exc}") from exc

    prefix = (
        "Crawlability confirmed. "
        if crawlability["verdict"] == "allowed"
        else "Crawlability uncertain — proceeding carefully. "
    )
    return {
        "status": "queued",
        "started": True,
        "run_id": run.id,
        "source_id": source_id,
        "message": prefix + f"Crawl queued as run #{run.id}. Scraper will pick it up shortly.",
        "crawlability": crawlability,
    }


@router.post("/sources/{source_id}/crawl-exclusive")
def trigger_crawl_exclusive(
    source_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_roles("superadmin", "reviewer")),
):
    """Pause schedule, cancel other active crawls, and queue only this source immediately."""
    from datetime import datetime, timezone

    from app.config import get_settings
    from scraper.crawl_control import (
        clear_queue,
        control_status,
        pause_schedule,
        push_crawl_job,
        request_abort_others,
    )

    now = datetime.now(timezone.utc)
    settings = get_settings()

    src = db.query(GovernmentSource).filter(GovernmentSource.id == source_id).first()
    if not src:
        raise HTTPException(404, "Source not found")
    if not src.enabled:
        raise HTTPException(400, "Source is disabled. Enable it after review, then crawl.")

    crawlability = probe_crawlability(src.base_url, settings.crawler_user_agent)
    src.robots_allowed = crawlability["robots_allowed"]
    src.last_checked = now
    if crawlability["verdict"] == "blocked":
        src.status = "MANUAL/RESTRICTED"
        write_audit(
            db,
            admin,
            "trigger_crawl_exclusive_blocked",
            "government_source",
            source_id,
            {"crawlability": crawlability},
        )
        db.commit()
        return {
            "status": "blocked",
            "started": False,
            "source_id": source_id,
            "message": crawlability["summary"],
            "crawlability": crawlability,
        }
    if crawlability["verdict"] == "allowed":
        src.status = "ACTIVE"
    else:
        src.status = "WARNING"

    # Cancel every other active crawl (and any previous run for this source)
    others = (
        db.query(ScrapingRun)
        .filter(
            ScrapingRun.status.in_(("queued", "running")),
            ScrapingRun.end_time.is_(None),
        )
        .all()
    )
    paused_ids = []
    for run in others:
        run.status = "cancelled"
        run.end_time = now
        run.notes = ((run.notes or "") + " | paused for exclusive crawl").strip(" |")
        paused_ids.append(run.id)

    run = ScrapingRun(
        source_id=source_id,
        status="queued",
        notes="exclusive crawl — schedule paused; other crawls cancelled",
    )
    db.add(run)
    db.flush()

    try:
        clear_queue(settings.redis_url)
        pause_schedule(settings.redis_url, exclusive_run_id=run.id)
        request_abort_others(settings.redis_url, keep_run_id=run.id)
        push_crawl_job(settings.redis_url, source_id, run.id)
    except Exception as exc:
        run.status = "failed"
        run.end_time = now
        run.notes = ((run.notes or "") + f" | exclusive queue failed: {exc}").strip(" |")
        db.commit()
        raise HTTPException(500, f"Could not start exclusive crawl: {exc}") from exc

    write_audit(
        db,
        admin,
        "trigger_crawl_exclusive",
        "government_source",
        source_id,
        {"run_id": run.id, "paused_runs": paused_ids, "crawlability": crawlability},
    )
    db.commit()
    db.refresh(run)

    status = control_status(settings.redis_url)
    return {
        "status": "queued",
        "started": True,
        "run_id": run.id,
        "source_id": source_id,
        "paused_runs": paused_ids,
        "schedule_paused": True,
        "control": status,
        "message": (
            f"Paused {len(paused_ids)} other crawl(s) and scheduled tick. "
            f"Exclusive crawl queued as run #{run.id}. "
            "Use Resume schedule when finished if you want periodic crawls again."
        ),
        "crawlability": crawlability,
    }


@router.post("/crawls/resume-schedule")
def resume_crawl_schedule(
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_roles("superadmin", "reviewer")),
):
    """Re-enable the scraper schedule after an exclusive crawl pause."""
    from app.config import get_settings
    from scraper.crawl_control import control_status, resume_schedule

    settings = get_settings()
    try:
        resume_schedule(settings.redis_url)
    except Exception as exc:
        raise HTTPException(500, f"Could not resume schedule: {exc}") from exc

    write_audit(db, admin, "resume_crawl_schedule", "scraping_run", details={})
    db.commit()
    return {
        "resumed": True,
        "message": "Scraper schedule resumed. Periodic and queued crawls can run again.",
        "control": control_status(settings.redis_url),
    }


@router.get("/crawls/control")
def crawl_control_status(
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    from app.config import get_settings
    from scraper.crawl_control import control_status

    settings = get_settings()
    try:
        status = control_status(settings.redis_url)
    except Exception as exc:
        raise HTTPException(500, f"Could not read crawl control: {exc}") from exc
    return status


@router.post("/crawls/clear-stuck")
def clear_stuck_crawls(
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_roles("superadmin", "reviewer")),
):
    """Mark orphaned queued/running crawls as failed and empty the Redis crawl queue."""
    from datetime import datetime, timezone

    from app.config import get_settings

    stuck = (
        db.query(ScrapingRun)
        .filter(
            ScrapingRun.status.in_(("queued", "running")),
            ScrapingRun.end_time.is_(None),
        )
        .all()
    )
    now = datetime.now(timezone.utc)
    for run in stuck:
        run.status = "failed"
        run.end_time = now
        run.notes = ((run.notes or "") + " | cleared by admin").strip(" |")

    redis_cleared = 0
    try:
        import redis

        settings = get_settings()
        r = redis.from_url(settings.redis_url, decode_responses=True)
        redis_cleared = int(r.delete("yojana:crawl_now") or 0)
        from scraper.crawl_control import resume_schedule

        resume_schedule(settings.redis_url)
        r.close()
    except Exception:
        redis_cleared = 0

    write_audit(
        db,
        admin,
        "clear_stuck_crawls",
        "scraping_run",
        details={"count": len(stuck), "redis_cleared": redis_cleared},
    )
    db.commit()
    return {
        "cleared": len(stuck),
        "run_ids": [r.id for r in stuck],
        "redis_queue_cleared": bool(redis_cleared),
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


@router.post("/changes/approve-all")
def approve_all_changes(
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_roles("superadmin", "reviewer")),
):
    """Approve every change currently waiting for review."""
    from scraper.change_detection.promote import apply_change

    pending = (
        db.query(DataChange)
        .filter(DataChange.status.in_(["pending_review", "detected"]))
        .order_by(DataChange.id.asc())
        .all()
    )
    approved_ids: list[int] = []
    for change in pending:
        apply_change(db, change, True, admin.id)
        approved_ids.append(change.id)

    write_audit(
        db,
        admin,
        "approve_all_changes",
        "data_change",
        details={"count": len(approved_ids), "ids": approved_ids[:200]},
    )
    db.commit()
    return {
        "ok": True,
        "approved": len(approved_ids),
        "ids": approved_ids,
        "message": (
            f"Approved {len(approved_ids)} change(s)."
            if approved_ids
            else "No pending changes to approve."
        ),
    }


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
