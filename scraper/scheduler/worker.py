"""APScheduler worker for periodic source checks."""

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

from app.database.session import SessionLocal
from app.models import GovernmentSource
from app.seed import seed
from scraper.spiders.http_crawler import SourceCrawler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scraper.scheduler")


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


def tick() -> None:
    db = SessionLocal()
    try:
        for source in due_sources(db):
            logger.info("Scheduled crawl: %s", source.source_name)
            try:
                SourceCrawler(db, source).crawl()
            except Exception:
                logger.exception("Crawl failed for %s — keeping existing data", source.source_name)
                source.status = "WARNING"
                db.commit()
    finally:
        db.close()


def main() -> None:
    seed()
    scheduler = BackgroundScheduler()
    scheduler.add_job(tick, "interval", minutes=5, id="source_tick", max_instances=1)
    scheduler.start()
    logger.info("Scheduler started; checking due sources every 5 minutes")
    # Run once at startup
    tick()
    try:
        while True:
            time.sleep(30)
    except KeyboardInterrupt:
        scheduler.shutdown()


if __name__ == "__main__":
    main()
