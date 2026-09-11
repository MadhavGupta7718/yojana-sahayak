"""Force re-ingestion helpers for development/demo."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.database.session import SessionLocal
from app.models import RawDocument
from scraper.run import run_all


def main() -> None:
    db = SessionLocal()
    try:
        # Clear hashes so change detection reprocesses pages without deleting production schemes first
        deleted = db.query(RawDocument).delete()
        db.commit()
        print(f"Cleared {deleted} raw_documents hashes for reprocessing")
    finally:
        db.close()
    run_all("NSFDC")


if __name__ == "__main__":
    main()
