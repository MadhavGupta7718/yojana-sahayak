"""APScheduler worker for periodic source checks + on-demand admin crawl queue."""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.database.session import SessionLocal
from app.models import GovernmentSource, ScrapingRun
from app.seed import seed
from scraper.spiders.http_crawler import SourceCrawler

logging.basicConfig(level=logging.INFO)
# Drain ticks every 5s; long crawls hold the only instance, so APScheduler would
# WARNING-spam "maximum number of running instances reached". That is expected.
logging.getLogger("apscheduler").setLevel(logging.ERROR)
logger = logging.getLogger("scraper.scheduler")

CRAWL_QUEUE_KEY = "yojana:crawl_now"


def due_sources(db) -> list[GovernmentSource]:
    now = datetime.now(timezone.utc)
    sources = db.query(GovernmentSource).filter(GovernmentSource.enabled.is_(True)).all()
    due = []
    for s in sources:
        if s.status == "MANUAL/RESTRICTED":
            continue
        freq = s.crawl_frequency or 15
        if s.last_checked is None:
            due.append(s)
            continue
        last = s.last_checked
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        minutes = (now - last).total_seconds() / 60
        if minutes >= freq:
            due.append(s)
    return due


def run_source_crawl(source_id: int, reason: str = "scheduled", run_id: int | None = None) -> None:
    db = SessionLocal()
    try:
        source = db.query(GovernmentSource).filter(GovernmentSource.id == source_id).first()
        if not source:
            logger.warning("Crawl skipped — source %s not found (%s)", source_id, reason)
            return
        if not source.enabled:
            logger.warning("Crawl skipped — source %s is disabled (%s)", source.source_name, reason)
            if run_id:
                queued = db.query(ScrapingRun).filter(ScrapingRun.id == run_id).first()
                if queued and queued.status == "queued":
                    queued.status = "failed"
                    queued.end_time = datetime.now(timezone.utc)
                    queued.notes = ((queued.notes or "") + " | source disabled").strip(" |")
                    db.commit()
            return
        logger.info("Starting crawl (%s): %s [%s]", reason, source.source_name, source.base_url)
        run = SourceCrawler(db, source).crawl(run_id=run_id)
        logger.info(
            "Crawl finished (%s): %s status=%s pages=%s docs=%s changes=%s errors=%s",
            reason,
            source.source_name,
            run.status,
            run.pages_crawled,
            run.documents_processed,
            run.changes_detected,
            run.error_count,
        )
    except Exception:
        logger.exception("Crawl failed for source_id=%s (%s)", source_id, reason)
        try:
            source = db.query(GovernmentSource).filter(GovernmentSource.id == source_id).first()
            if source:
                source.status = "WARNING"
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def tick() -> None:
    db = SessionLocal()
    try:
        for source in due_sources(db):
            run_source_crawl(source.id, reason="scheduled")
    finally:
        db.close()


def drain_on_demand_queue(max_jobs: int = 3) -> None:
    """Pick up admin 'Crawl now' jobs from Redis."""
    try:
        import redis
    except ImportError:
        return

    settings = get_settings()
    try:
        client = redis.from_url(settings.redis_url, decode_responses=True)
    except Exception:
        logger.exception("Redis unavailable for crawl queue")
        return

    try:
        for _ in range(max_jobs):
            item = client.rpop(CRAWL_QUEUE_KEY)
            if not item:
                break
            run_id = None
            try:
                if ":" in item:
                    source_part, run_part = item.split(":", 1)
                    source_id = int(source_part)
                    run_id = int(run_part)
                else:
                    source_id = int(item)
            except ValueError:
                logger.warning("Invalid crawl queue payload: %s", item)
                continue
            run_source_crawl(source_id, reason="admin-queue", run_id=run_id)
    finally:
        try:
            client.close()
        except Exception:
            pass


def main() -> None:
    seed()
    scheduler = BackgroundScheduler()
    scheduler.add_job(tick, "interval", minutes=5, id="source_tick", max_instances=1)
    scheduler.add_job(drain_on_demand_queue, "interval", seconds=5, id="crawl_queue", max_instances=1)
    scheduler.start()
    logger.info("Scheduler started; due sources every 5m, admin crawl queue every 5s")
    # Run once at startup
    tick()
    drain_on_demand_queue()
    try:
        while True:
            time.sleep(30)
    except KeyboardInterrupt:
        scheduler.shutdown()


if __name__ == "__main__":
    main()
