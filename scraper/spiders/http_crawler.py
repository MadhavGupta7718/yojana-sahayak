"""HTTP-first NSFDC and multi-source crawler."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import GovernmentSource, RawDocument, ScrapingError, ScrapingRun, StagingRecord
from scraper.change_detection.promote import promote_staging
from scraper.extractors.facts import (
    extract_document_schemes,
    extract_partner_categories,
    extract_partners,
)
from scraper.extractors.scheme_gate import is_loan_scheme_payload, is_non_scheme_document
from scraper.extractors.normalize import canonical_key, content_hash
from scraper.extractors.nsfdc import extract_nsfdc_eligibility, extract_nsfdc_schemes
from scraper.parsers.content import extract_links, extract_pdf_text, html_title, html_to_text
from scraper.validators.robots import check_robots

RELEVANT_KEYWORDS = [
    "scheme",
    "loan",
    "finance",
    "lending",
    "channel",
    "partner",
    "sca",
    "eligibility",
    "guideline",
    "circular",
    "notification",
    "faq",
    "micro",
    "education",
    "interest",
    "repayment",
    "policy",
]


class SourceCrawler:
    def __init__(self, db: Session, source: GovernmentSource, force_refresh: bool = False):
        self.db = db
        self.source = source
        self.settings = get_settings()
        self.ua = self.settings.crawler_user_agent
        self.delay = self.settings.crawl_delay_seconds
        self.run: Optional[ScrapingRun] = None
        self.force_refresh = force_refresh

    def crawl(self, run_id: int | None = None, force_refresh: bool | None = None) -> ScrapingRun:
        if force_refresh is not None:
            self.force_refresh = force_refresh
        if run_id is not None:
            existing = self.db.query(ScrapingRun).filter(ScrapingRun.id == run_id).first()
            if existing and existing.source_id == self.source.id and existing.status in ("queued", "running"):
                self.run = existing
                self.run.status = "running"
                self.run.notes = ((self.run.notes or "") + " | claimed by scraper").strip(" |")
                # Admin-queued runs must re-read pages even if ETag/hash unchanged
                if "queued by admin" in (self.run.notes or "") or "exclusive" in (self.run.notes or "").lower():
                    self.force_refresh = True
                self.db.commit()
            elif existing and existing.status == "failed":
                # Cleared while waiting — do not restart
                return existing
            else:
                self.run = ScrapingRun(source_id=self.source.id, status="running")
                self.db.add(self.run)
                self.db.commit()
                self.db.refresh(self.run)
        else:
            queued = (
                self.db.query(ScrapingRun)
                .filter(
                    ScrapingRun.source_id == self.source.id,
                    ScrapingRun.status == "queued",
                    ScrapingRun.end_time.is_(None),
                )
                .order_by(ScrapingRun.id.desc())
                .first()
            )
            if queued:
                self.run = queued
                self.run.status = "running"
                self.run.notes = ((self.run.notes or "") + " | claimed by scraper").strip(" |")
                if "queued by admin" in (self.run.notes or "") or "exclusive" in (self.run.notes or "").lower():
                    self.force_refresh = True
                self.db.commit()
            else:
                self.run = ScrapingRun(source_id=self.source.id, status="running")
                self.db.add(self.run)
                self.db.commit()
                self.db.refresh(self.run)

        try:
            allowed, notes = check_robots(self.source.base_url, self.ua)
            self.source.robots_allowed = allowed
            self.source.last_checked = datetime.now(timezone.utc)
            # Replace robots note instead of appending forever
            base_notes = re.sub(r"\s*\|\s*robots:.*$", "", (self.source.notes or "").strip())
            self.source.notes = (f"{base_notes} | robots: {notes}".strip(" |") if base_notes else f"robots: {notes}")
            if allowed is False:
                self.source.status = "MANUAL/RESTRICTED"
                self.run.status = "restricted"
                self.run.notes = notes
                self.run.end_time = datetime.now(timezone.utc)
                self.db.commit()
                return self.run
            if allowed is None:
                self.source.status = "WARNING"
            else:
                self.source.status = "ACTIVE"

            visited: set[str] = set()
            queue = [self.source.base_url]
            # NSFDC-only deep seeds — do not hit these on Netlify / other portals
            host = urlparse(self.source.base_url).netloc.lower()
            if "nsfdc" in host:
                for path in [
                    "scheme",
                    "eligibility-requirements",
                    "our-channel-partners",
                    "how-to-apply",
                    "indicative-activities",
                    "faqs",
                    "beneficiary-guidelines",
                    "guiding-principles",
                    "about-us-3",
                ]:
                    queue.append(urljoin(self.source.base_url, path))

            with httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": self.ua}) as client:
                while queue and len(visited) < 80:
                    if self._should_abort():
                        self.run.status = "cancelled"
                        self.run.notes = ((self.run.notes or "") + " | cancelled for exclusive crawl").strip(" |")
                        self.db.commit()
                        return self.run
                    url = queue.pop(0)
                    if url in visited:
                        continue
                    visited.add(url)
                    time.sleep(self.delay)
                    try:
                        self._process_url(client, url, queue, visited)
                    except Exception as exc:
                        self._error("fetch_error", str(exc), url)

            self.source.last_successful_crawl = datetime.now(timezone.utc)
            if self.source.status != "WARNING":
                self.source.status = "ACTIVE"
            self._refresh_partner_scheme_mappings()
            self.run.status = "success"
            self.run.notes = (
                (self.run.notes or "")
                + f" | done pages={self.run.pages_crawled} docs={self.run.documents_processed} "
                f"changes={self.run.changes_detected} errors={self.run.error_count}"
                + (" | force_refresh" if self.force_refresh else "")
            ).strip(" |")
        except Exception as exc:
            self._error("run_error", str(exc), self.source.base_url)
            self.source.status = "WARNING"
            self.run.status = "failed"
            # Do NOT delete existing production data
        finally:
            self.run.end_time = datetime.now(timezone.utc)
            self.db.commit()
            self._clear_abort_if_exclusive_finished()
        return self.run

    def _should_abort(self) -> bool:
        try:
            from scraper.crawl_control import should_abort_run

            return should_abort_run(self.settings.redis_url, self.run.id if self.run else None)
        except Exception:
            return False

    def _clear_abort_if_exclusive_finished(self) -> None:
        """If this run was the exclusive keep-run, clear abort flag so future crawls work."""
        try:
            from scraper.crawl_control import clear_exclusive_abort_if_match

            clear_exclusive_abort_if_match(self.settings.redis_url, self.run.id if self.run else None)
        except Exception:
            pass

    def _refresh_partner_scheme_mappings(self) -> None:
        from app.models import Partner, PartnerSchemeMapping, Scheme

        schemes = (
            self.db.query(Scheme)
            .filter(Scheme.source_id == self.source.id, Scheme.status == "active")
            .all()
        )
        partners = (
            self.db.query(Partner)
            .filter(Partner.source_id == self.source.id, Partner.status == "active")
            .all()
        )
        for p in partners:
            for s in schemes:
                exists = (
                    self.db.query(PartnerSchemeMapping)
                    .filter_by(partner_id=p.id, scheme_id=s.id)
                    .first()
                )
                if not exists:
                    self.db.add(
                        PartnerSchemeMapping(
                            partner_id=p.id,
                            scheme_id=s.id,
                            eligibility_status="eligible",
                            source_id=self.source.id,
                        )
                    )

    def _process_url(self, client: httpx.Client, url: str, queue: list[str], visited: set[str]) -> None:
        # Relevance gate for non-root pages
        path = urlparse(url).path.lower()
        if url.rstrip("/") != self.source.base_url.rstrip("/") and not any(k in path or k in url.lower() for k in RELEVANT_KEYWORDS):
            # Still allow homepage-linked PDF docs later via extension
            if not url.lower().endswith(".pdf"):
                return

        head_headers = {}
        etag = None
        last_mod = None
        try:
            head = client.head(url)
            # Some hosts (incl. CDNs) answer HEAD poorly; only trust 2xx
            if 200 <= head.status_code < 300:
                etag = head.headers.get("ETag")
                last_mod = head.headers.get("Last-Modified")
                head_headers = {"ETag": etag, "Last-Modified": last_mod}
        except Exception:
            etag = None
            last_mod = None

        # Change detection via previous hash/etag (skipped on admin force refresh)
        prev = (
            self.db.query(RawDocument)
            .filter(RawDocument.source_id == self.source.id, RawDocument.url == url)
            .order_by(RawDocument.id.desc())
            .first()
        )
        if (
            not self.force_refresh
            and prev
            and etag
            and prev.http_etag
            and prev.http_etag == etag
        ):
            return

        resp = client.get(url)
        self.run.pages_crawled += 1
        if resp.status_code == 403 or resp.status_code == 401:
            self.source.status = "MANUAL/RESTRICTED"
            self._error("access_restricted", f"HTTP {resp.status_code}", url)
            return
        if resp.status_code >= 400:
            self._error("http_error", f"HTTP {resp.status_code}", url)
            return

        content_type = (resp.headers.get("content-type") or "").lower()
        is_pdf = "pdf" in content_type or url.lower().endswith(".pdf")

        if is_pdf:
            text = extract_pdf_text(resp.content)
            title = url.split("/")[-1]
            ctype = "pdf"
        else:
            html = resp.text
            text = html_to_text(html)
            title = html_title(html)
            ctype = "html"
            # Enqueue relevant links
            for link in extract_links(html, self.source.base_url):
                if link not in visited and any(k in link.lower() for k in RELEVANT_KEYWORDS + [".pdf"]):
                    queue.append(link)

        if not text or len(text.strip()) < 40:
            return

        digest = content_hash(text)
        if not self.force_refresh and prev and prev.content_hash == digest:
            return  # no change

        self.source.last_changed = datetime.now(timezone.utc)
        raw = RawDocument(
            source_id=self.source.id,
            url=url,
            title=title,
            content_type=ctype,
            content_hash=digest,
            http_etag=etag,
            http_last_modified=last_mod,
            raw_text=text[:200000],
            metadata_json=head_headers,
            scraping_run_id=self.run.id,
        )
        self.db.add(raw)
        self.db.flush()
        self.run.documents_processed += 1

        # Policy / FAQ / portal chrome: keep raw hash for change detection, never create Scheme rows
        if is_non_scheme_document(url, title or "", text or ""):
            self.db.commit()
            return

        # Differential extraction — NSFDC-aware first
        staged_any = False
        nsfdc_schemes = extract_nsfdc_schemes(text, url)
        for scheme_data in nsfdc_schemes:
            payload = scheme_data["payload"]
            if not is_loan_scheme_payload(
                payload, url=url, text=str(payload.get("description") or "") or text
            ):
                continue
            staging = StagingRecord(
                source_id=self.source.id,
                raw_document_id=raw.id,
                entity_type="scheme",
                entity_key=payload.get("canonical_key") or canonical_key(payload.get("name") or url),
                payload=payload,
                original_text=scheme_data.get("original_text"),
                confidence=0.85,
                status="pending",
                source_url=url,
            )
            self.db.add(staging)
            self.db.flush()
            changes = promote_staging(self.db, staging)
            self.run.changes_detected += len(changes)
            staged_any = True

        elig = extract_nsfdc_eligibility(text, url)
        if elig and elig.get("max_income") is not None:
            # Update all NSFDC schemes missing income with official ceiling
            from app.models import Scheme

            schemes = (
                self.db.query(Scheme)
                .filter(Scheme.source_id == self.source.id, Scheme.status == "active")
                .all()
            )
            for sch in schemes:
                if not is_loan_scheme_payload(
                    {
                        "name": sch.name,
                        "scheme_type": sch.scheme_type,
                        "max_loan": sch.max_loan,
                        "min_loan": sch.min_loan,
                        "interest_rate": sch.interest_rate,
                        "tenure": sch.tenure,
                        "max_income": sch.max_income,
                        "description": sch.description,
                        "source_url": sch.source_url,
                    },
                    url=sch.source_url or url,
                    text=sch.description or "",
                ):
                    continue
                if sch.max_income is None:
                    sch.max_income = elig["max_income"]
                if not sch.beneficiary_requirements:
                    sch.beneficiary_requirements = elig.get("beneficiary_requirements")
                if elig.get("application_process") and not sch.application_process:
                    sch.application_process = elig["application_process"]
                sch.source_url = sch.source_url or url
            # Apply shared eligibility onto real NSFDC schemes only — do not create a fake scheme row
            staged_any = True

        if not staged_any:
            # Generic multi-scheme extraction for any published scheme page/PDF
            title_l = (title or "").lower()
            url_l_check = url.lower()
            looks_like_schemes = (
                "scheme name:" in text.lower()
                or any(k in url_l_check for k in ["scheme", "loan", "finance", "lending", "yojana", "credit"])
                or any(k in title_l for k in ["scheme", "loan", "finance", "credit", "yojana"])
            )
            # Avoid treating bare eligibility pages as schemes unless they carry scheme blocks
            if "eligib" in url_l_check and "scheme name:" not in text.lower():
                looks_like_schemes = False
            if "home" not in title_l or "scheme name:" in text.lower():
                if looks_like_schemes:
                    for scheme_data in extract_document_schemes(text, title, url):
                        payload = scheme_data["payload"]
                        if not is_loan_scheme_payload(payload, url=url, text=text):
                            continue
                        staging = StagingRecord(
                            source_id=self.source.id,
                            raw_document_id=raw.id,
                            entity_type="scheme",
                            entity_key=payload.get("canonical_key") or canonical_key(payload.get("name") or url),
                            payload=payload,
                            original_text=scheme_data.get("original_text"),
                            confidence=0.7,
                            status="pending",
                            source_url=url,
                        )
                        self.db.add(staging)
                        self.db.flush()
                        changes = promote_staging(self.db, staging)
                        self.run.changes_detected += len(changes)
                        staged_any = True
                        for partner in scheme_data.get("partners") or []:
                            pst = StagingRecord(
                                source_id=self.source.id,
                                raw_document_id=raw.id,
                                entity_type="partner",
                                entity_key=partner["canonical_key"],
                                payload=partner,
                                original_text={"name": partner["name"]},
                                confidence=0.75,
                                status="pending",
                                source_url=url,
                            )
                            self.db.add(pst)
                            self.db.flush()
                            self.run.changes_detected += len(promote_staging(self.db, pst))

        # Partner extraction: require partner-page URL or explicit partner cue (word-boundary for SCA)
        url_l = url.lower()
        partner_url = any(
            k in url_l
            for k in (
                "channel-partner",
                "channel_partner",
                "our-channel-partners",
                "channelising",
                "channelizing",
            )
        )
        partner_text = bool(
            re.search(r"\b(channel\s*partners?|channelising|channelizing|state\s+channelizing)\b", text, re.I)
            or re.search(r"\bSCAs?\b", text)
        )
        blocked_url = any(b in url_l for b in ("career", "recruit", "interview", "vacancy", "/hr", "pratibha"))
        if (partner_url or partner_text) and not blocked_url:
            # Skip if this page already promoted structured per-scheme partners
            already_structured = staged_any and "channel partner name:" in text.lower()
            if not already_structured:
                partner_payloads = extract_partners(text, url) + extract_partner_categories(text, url)
                for partner in partner_payloads:
                    staging = StagingRecord(
                        source_id=self.source.id,
                        raw_document_id=raw.id,
                        entity_type="partner",
                        entity_key=partner["canonical_key"],
                        payload=partner,
                        original_text={"name": partner["name"]},
                        confidence=0.5,
                        status="pending",
                        source_url=url,
                    )
                    self.db.add(staging)
                    self.db.flush()
                    changes = promote_staging(self.db, staging)
                    self.run.changes_detected += len(changes)

        self.db.commit()

    def _error(self, error_type: str, message: str, url: Optional[str] = None) -> None:
        self.run.error_count += 1
        self.db.add(
            ScrapingError(
                scraping_run_id=self.run.id if self.run else None,
                source_id=self.source.id,
                url=url,
                error_type=error_type,
                message=message[:4000],
            )
        )
        self.db.commit()
