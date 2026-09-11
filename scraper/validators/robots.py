"""Robots.txt respect helper."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx


def check_robots(base_url: str, user_agent: str, timeout: float = 15.0) -> tuple[bool | None, str]:
    """Return (allowed_for_base_crawl, notes). None means could not determine."""
    parsed = urlparse(base_url)
    robots_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(robots_url, headers={"User-Agent": user_agent})
            if resp.status_code == 404:
                return True, "No robots.txt found; proceeding politely with default crawl delay."
            if resp.status_code >= 400:
                return None, f"Could not fetch robots.txt (HTTP {resp.status_code})."
            rp = RobotFileParser()
            rp.parse(resp.text.splitlines())
            # Check root path allow
            allowed = rp.can_fetch(user_agent, base_url)
            if not allowed:
                # Also try with *
                allowed = rp.can_fetch("*", base_url)
            if not allowed:
                return False, "robots.txt disallows crawling for this user-agent/path."
            return True, "robots.txt allows crawling."
    except Exception as exc:
        return None, f"robots.txt check failed: {exc}"
