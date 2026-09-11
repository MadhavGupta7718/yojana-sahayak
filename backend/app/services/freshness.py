from datetime import datetime, timezone
from typing import Optional

from app.config import get_settings


def freshness_state(last_verified: Optional[datetime]) -> str:
    if last_verified is None:
        return "Unknown"
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if last_verified.tzinfo is None:
        last_verified = last_verified.replace(tzinfo=timezone.utc)
    days = (now - last_verified).total_seconds() / 86400
    if days <= settings.freshness_fresh_days:
        return "Fresh"
    if days <= settings.freshness_aging_days:
        return "Aging"
    return "Stale"


def format_unavailable(value):
    if value is None or value == "" or value == []:
        return None
    return value
