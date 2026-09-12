"""Pre-crawl probe: robots.txt + homepage reachability."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from scraper.validators.robots import check_robots


def probe_crawlability(
    base_url: str,
    user_agent: str,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """
    Confirm whether an official website can be crawled politely.

    verdict:
      - allowed: robots OK (or missing) and homepage reachable
      - blocked: robots disallow or HTTP auth/forbidden
      - uncertain: robots unknown or soft failures; crawl may still be attempted carefully
    """
    robots_allowed, robots_notes = check_robots(base_url, user_agent, timeout=timeout)
    http_status: Optional[int] = None
    http_ok = False
    homepage_notes = ""
    content_type = ""
    final_url = base_url

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(base_url, headers={"User-Agent": user_agent})
            http_status = resp.status_code
            final_url = str(resp.url)
            content_type = (resp.headers.get("content-type") or "").split(";")[0].strip()
            if resp.status_code in (401, 403):
                homepage_notes = f"Homepage blocked (HTTP {resp.status_code}). Use Manual upload."
            elif resp.status_code >= 400:
                homepage_notes = f"Homepage returned HTTP {resp.status_code}."
            else:
                http_ok = True
                body_len = len(resp.text or "")
                homepage_notes = f"Homepage reachable (HTTP {resp.status_code}, ~{body_len} chars)."
    except Exception as exc:
        homepage_notes = f"Homepage request failed: {exc}"

    if robots_allowed is False or http_status in (401, 403):
        verdict = "blocked"
        can_crawl = False
    elif robots_allowed is True and http_ok:
        verdict = "allowed"
        can_crawl = True
    elif http_ok and robots_allowed is None:
        verdict = "uncertain"
        can_crawl = True  # polite attempt allowed with warning
    elif robots_allowed is True and not http_ok:
        verdict = "uncertain"
        can_crawl = False
    else:
        verdict = "uncertain"
        can_crawl = False

    if verdict == "allowed":
        summary = "Yes — website can be crawled (robots allow + homepage reachable)."
    elif verdict == "blocked":
        summary = "No — crawling is restricted. Prefer Manual upload of official PDF/HTML."
    else:
        summary = "Uncertain — robots or homepage check was incomplete. Proceed only if you accept the risk."

    return {
        "verdict": verdict,
        "can_crawl": can_crawl,
        "summary": summary,
        "robots_allowed": robots_allowed,
        "robots_notes": robots_notes,
        "http_status": http_status,
        "http_ok": http_ok,
        "homepage_notes": homepage_notes,
        "content_type": content_type or None,
        "final_url": final_url,
        "user_agent": user_agent,
    }
