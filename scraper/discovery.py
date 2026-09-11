"""Constrained discovery of additional official government sources."""

from __future__ import annotations

from urllib.parse import urlparse

GOV_SUFFIXES = (".gov.in", ".nic.in")

KEYWORDS = [
    "NSFDC",
    "SC loan scheme",
    "Scheduled Caste financial assistance",
    "SC entrepreneur loan",
    "educational loan Scheduled Caste",
    "government concessional loan",
    "channelizing agency",
    "social justice loan scheme",
]


def is_government_domain(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host.endswith(sfx) or f".{sfx[1:]}" in host for sfx in [".gov.in", ".nic.in"]) or host.endswith(
        "gov.in"
    ) or host.endswith("nic.in")


def authority_relevance_score(url: str, title: str = "", snippet: str = "") -> tuple[int, str]:
    """Return (score, reason). Does NOT auto-enable sources."""
    if not is_government_domain(url):
        return 0, "Rejected: not a government domain"
    text = f"{url} {title} {snippet}".lower()
    hits = [k for k in KEYWORDS if k.lower() in text]
    score = 40 + 10 * len(hits)
    if "nsfdc" in text:
        score += 20
    if "socialjustice" in text or "social justice" in text:
        score += 15
    return min(score, 100), f"Candidate government source; keyword hits={hits}. Requires admin approval."


def propose_source(url: str, title: str = "", organization: str = "") -> dict:
    score, reason = authority_relevance_score(url, title)
    return {
        "base_url": url,
        "source_name": title or urlparse(url).netloc,
        "organization": organization or "Unknown government organization",
        "source_type": "discovered",
        "authority_level": score,
        "enabled": False,
        "discovery_status": "pending_review",
        "notes": reason,
        "auto_trusted": False,
    }
