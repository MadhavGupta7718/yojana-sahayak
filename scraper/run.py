"""Manual ingestion entrypoint: python -m scraper.run"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure imports work when run as module
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.database.session import SessionLocal
from app.models import GovernmentSource
from app.seed import seed
from scraper.spiders.http_crawler import SourceCrawler


def run_all(source_name: str | None = None) -> None:
    seed()
    db = SessionLocal()
    try:
        q = db.query(GovernmentSource).filter(GovernmentSource.enabled.is_(True))
        if source_name:
            q = q.filter(GovernmentSource.source_name == source_name)
        sources = q.all()
        if not sources:
            print("No enabled sources found.")
            return
        for source in sources:
            print(f"Crawling {source.source_name} ({source.base_url}) ...")
            run = SourceCrawler(db, source).crawl()
            print(
                f"  status={run.status} pages={run.pages_crawled} docs={run.documents_processed} "
                f"changes={run.changes_detected} errors={run.error_count}"
            )
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run government source ingestion")
    parser.add_argument("--source", help="Optional source_name filter, e.g. NSFDC")
    args = parser.parse_args()
    run_all(args.source)


if __name__ == "__main__":
    main()
