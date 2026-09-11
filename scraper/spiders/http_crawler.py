"""HTTP-first NSFDC and multi-source crawler."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import GovernmentSource, RawDocument, ScrapingError, ScrapingRun, StagingRecord
from scraper.change_detection.promote import promote_staging
from scraper.extractors.facts import extract_partner_categories, extract_partners, extract_scheme_fields
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
    def __init__(self, db: Session, source: GovernmentSource):
        self.db = db
        self.source = source
        self.settings = get_settings()
        self.ua = self.settings.crawler_user_agent
        self.delay = self.settings.crawl_delay_seconds
        self.run: Optional[ScrapingRun] = None

    def crawl(self) -> ScrapingRun:
        self.run = ScrapingRun(source_id=self.source.id, status="running")
        self.db.add(self.run)
        self.db.commit()
        self.db.refresh(self.run)

        try:
            allowed, notes = check_robots(self.source.base_url, self.ua)
            self.source.robots_allowed = allowed
            self.source.last_checked = datetime.now(timezone.utc)
            self.source.notes = (self.source.notes or "") + f" | robots: {notes}"
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
            # Seed common NSFDC paths if present
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
        except Exception as exc:
            self._error("run_error", str(exc), self.source.base_url)
            self.source.status = "WARNING"
            self.run.status = "failed"
            # Do NOT delete existing production data
        finally:
            self.run.end_time = datetime.now(timezone.utc)
            self.db.commit()
        return self.run

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
        try:
            head = client.head(url)
            etag = head.headers.get("ETag")
            last_mod = head.headers.get("Last-Modified")
            head_headers = {"ETag": etag, "Last-Modified": last_mod}
        except Exception:
            etag = None
            last_mod = None

        # Change detection via previous hash/etag
        prev = (
            self.db.query(RawDocument)
            .filter(RawDocument.source_id == self.source.id, RawDocument.url == url)
            .order_by(RawDocument.id.desc())
            .first()
        )
        if prev and etag and prev.http_etag and prev.http_etag == etag:
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
        if prev and prev.content_hash == digest:
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

        # Differential extraction — NSFDC-aware first
        staged_any = False
        nsfdc_schemes = extract_nsfdc_schemes(text, url)
        for scheme_data in nsfdc_schemes:
            payload = scheme_data["payload"]
            # Attach shared eligibility if present on same crawl later via eligibility page
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
                if sch.max_income is None:
                    sch.max_income = elig["max_income"]
                if not sch.beneficiary_requirements:
                    sch.beneficiary_requirements = elig.get("beneficiary_requirements")
                if elig.get("application_process") and not sch.application_process:
                    sch.application_process = elig["application_process"]
                sch.source_url = sch.source_url or url
            # Also store eligibility as staging guidance-like record
            staging = StagingRecord(
                source_id=self.source.id,
                raw_document_id=raw.id,
                entity_type="scheme",
                entity_key="nsfdc-shared-eligibility",
                payload={
                    "name": "NSFDC Shared Eligibility Criteria",
                    "canonical_key": "nsfdc-shared-eligibility",
                    "max_income": elig.get("max_income"),
                    "beneficiary_requirements": elig.get("beneficiary_requirements"),
                    "application_process": elig.get("application_process"),
                    "purpose": "business",
                    "scheme_type": "eligibility_reference",
                    "description": "Shared eligibility criteria published by NSFDC for credit/loan-based schemes.",
                    "source_url": url,
                },
                original_text=elig.get("original_text"),
                confidence=0.9,
                status="pending",
                source_url=url,
            )
            self.db.add(staging)
            self.db.flush()
            changes = promote_staging(self.db, staging)
            self.run.changes_detected += len(changes)
            staged_any = True

        if not staged_any:
            # Generic fallback — skip pure navigation homepages
            title_l = (title or "").lower()
            if "home" not in title_l and (
                any(k in url.lower() for k in ["scheme", "loan", "finance", "lending", "eligib"])
            ):
                scheme_data = extract_scheme_fields(text, title, url)
                payload = scheme_data["payload"]
                if any(
                    k in (payload.get("name") or "").lower()
                    for k in ["scheme", "loan", "finance", "credit", "micro", "yojana"]
                ):
                    staging = StagingRecord(
                        source_id=self.source.id,
                        raw_document_id=raw.id,
                        entity_type="scheme",
                        entity_key=payload.get("canonical_key") or canonical_key(payload.get("name") or url),
                        payload=payload,
                        original_text=scheme_data.get("original_text"),
                        confidence=0.55,
                        status="pending",
                        source_url=url,
                    )
                    self.db.add(staging)
                    self.db.flush()
                    changes = promote_staging(self.db, staging)
                    self.run.changes_detected += len(changes)

        if any(k in url.lower() or k in text.lower() for k in ["channel partner", "channelising", "channelizing", "sca", "our-channel-partners"]):
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
