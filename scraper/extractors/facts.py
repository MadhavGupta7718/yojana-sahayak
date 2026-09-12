"""Extract structured scheme/partner facts from official page text."""

from __future__ import annotations

import re
from typing import Any, Optional

from scraper.extractors.normalize import (
    canonical_key,
    normalize_whitespace,
    parse_indian_amount,
    parse_months,
    parse_percent,
)

SCHEME_NAME_HINTS = [
    r"micro\s*credit\s*finance",
    r"micro\s*finance\s*scheme",
    r"term\s*loan",
    r"educational\s*loan",
    r"vocational\s*education",
    r"skill\s*development",
    r"stand[\-\s]*up",
    r"green\s*business",
    r"mahila\s*samriddhi",
    r"laghu\s*vyavasay",
    r"unit\s*cost",
    r"scheme",
]

FIELD_PATTERNS = {
    "max_loan": [
        r"(?:maximum|max\.?|upto|up to|ceiling)\s*(?:loan|finance|assistance)?[^\d₹rs]{0,40}((?:₹|rs\.?)?\s*[\d,.]+\s*(?:lakh|lac|crore)?)",
        r"(?:loan\s*limit|finance\s*limit)[^\d₹rs]{0,40}((?:₹|rs\.?)?\s*[\d,.]+\s*(?:lakh|lac|crore)?)",
    ],
    "min_loan": [
        r"(?:minimum|min\.?)\s*(?:loan|finance)[^\d₹rs]{0,40}((?:₹|rs\.?)?\s*[\d,.]+\s*(?:lakh|lac|crore)?)",
    ],
    "interest_rate": [
        r"(?:interest\s*rate|rate\s*of\s*interest|roi)[^\d%]{0,40}((?:[0-9]|1[0-9]|20)(?:\.\d+)?\s*%)",
        r"(?:charge[sd]?|beneficiary)[^\d%]{0,40}((?:[0-9]|1[0-9]|20)(?:\.\d+)?\s*%)",
    ],
    "max_income": [
        r"(?:annual\s*(?:family\s*)?income|income\s*limit|income\s*ceiling)[^\d₹rs]{0,40}((?:₹|rs\.?)?\s*[\d,.]+\s*(?:lakh|lac|crore)?)",
    ],
    "tenure": [
        r"(?:repayment|repayment\s*period|tenure|loan\s*period)[^\d]{0,30}(\d+\s*(?:years?|months?|वर्ष|महीने)?)",
    ],
    "moratorium": [
        r"(?:moratorium|gestation)[^\d]{0,30}(\d+\s*(?:years?|months)?)",
    ],
}


DOC_KEYWORDS = [
    "identity proof", "aadhaar", "aadhar", "pan", "address proof", "income certificate",
    "caste certificate", "project report", "bank account", "passport size", "educational",
    "ration card", "voter", "driving licence", "passport",
]


def _first_match(patterns: list[str], text: str) -> Optional[str]:
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return m.group(1)
    return None


def extract_scheme_fields(text: str, page_title: str | None = None, url: str = "") -> dict[str, Any]:
    clean = normalize_whitespace(text)
    title = page_title or ""
    # Prefer title if it looks like a scheme
    name = title
    if not any(re.search(h, name, re.I) for h in SCHEME_NAME_HINTS):
        # try find heading-like scheme mention
        for h in SCHEME_NAME_HINTS:
            m = re.search(rf"([A-Z][A-Za-z0-9 \-]{{5,80}}{h}[A-Za-z0-9 \-]{{0,40}})", text, re.I)
            if m:
                name = normalize_whitespace(m.group(1))
                break
    if not name:
        name = "Unnamed scheme from official page"

    payload: dict[str, Any] = {
        "name": name[:500],
        "canonical_key": canonical_key(name),
        "source_url": url,
        "description": clean[:2000] if clean else None,
    }
    originals: dict[str, str] = {}

    raw_max = _first_match(FIELD_PATTERNS["max_loan"], text)
    if raw_max:
        val, orig = parse_indian_amount(raw_max)
        payload["max_loan"] = val
        originals["max_loan"] = orig

    raw_min = _first_match(FIELD_PATTERNS["min_loan"], text)
    if raw_min:
        val, orig = parse_indian_amount(raw_min)
        payload["min_loan"] = val
        originals["min_loan"] = orig

    raw_rate = _first_match(FIELD_PATTERNS["interest_rate"], text)
    if raw_rate:
        val, orig = parse_percent(raw_rate)
        payload["interest_rate"] = val
        originals["interest_rate"] = orig

    raw_income = _first_match(FIELD_PATTERNS["max_income"], text)
    if raw_income:
        val, orig = parse_indian_amount(raw_income)
        payload["max_income"] = val
        originals["max_income"] = orig

    raw_tenure = _first_match(FIELD_PATTERNS["tenure"], text)
    if raw_tenure:
        val, orig = parse_months(raw_tenure)
        payload["tenure"] = val
        originals["tenure"] = orig

    raw_mora = _first_match(FIELD_PATTERNS["moratorium"], text)
    if raw_mora:
        val, orig = parse_months(raw_mora)
        payload["moratorium"] = val
        originals["moratorium"] = orig

    docs = []
    lower = text.lower()
    for dk in DOC_KEYWORDS:
        if dk in lower:
            docs.append(dk.title())
    if docs:
        payload["required_documents"] = sorted(set(docs))

    # Category hint for NSFDC
    if re.search(r"scheduled\s*caste|\bSC\b|अनुसूचित\s*जाति", text, re.I):
        payload["beneficiary_requirements"] = {"categories": ["SC"]}

    # Purpose heuristic
    if re.search(r"education|educational|vocational", text, re.I):
        payload["purpose"] = "education"
        payload["scheme_type"] = "educational_loan"
    elif re.search(r"micro|self[\-\s]*employment|business|enterprise", text, re.I):
        payload["purpose"] = "business"
        payload["scheme_type"] = "term_loan"

    return {"payload": payload, "original_text": originals}


def _is_partner_source_url(url: str) -> bool:
    u = (url or "").lower()
    blocked = ("career", "recruit", "interview", "vacancy", "hr/", "/hr", "tender", "pratibha", "upsc")
    if any(b in u for b in blocked):
        return False
    allowed = (
        "channel-partner",
        "channel_partner",
        "channelpartner",
        "our-channel-partners",
        "channelising",
        "channelizing",
        "/sca",
        "state-channel",
    )
    return any(a in u for a in allowed)


def _looks_like_person_or_job(name: str) -> bool:
    n = name or ""
    if re.match(r"^(Mr\.|Ms\.|Mrs\.|Shri|Smt\.?|Dr\.)\b", n, re.I):
        return True
    if re.search(r"\b(Manager|Deputy|Assistant|Officer|Director|Candidate|Selected|Interview)\b", n, re.I):
        return True
    if re.search(r"\b(Pay Scale|Level E-|IDA Pattern|UPSC)\b", n, re.I):
        return True
    return False


def extract_partners(text: str, url: str = "") -> list[dict[str, Any]]:
    """Extract channel partner / SCA mentions when structured lists exist."""
    if url and not _is_partner_source_url(url):
        # Only extract agency-like names from known partner pages (never careers/HR PDFs)
        return []

    partners = []
    for m in re.finditer(
        r"(?P<name>[A-Z][A-Za-z0-9 &.,\-()]{8,120}(?:Corporation|Corporation Ltd|Nigam|Board|Agency|Bank|Society))",
        text,
    ):
        name = normalize_whitespace(m.group("name"))
        if _looks_like_person_or_job(name):
            continue
        # NSFDC itself is the apex body, not a channel partner listing row
        if re.search(r"national scheduled castes finance", name, re.I):
            continue
        partners.append(
            {
                "name": name,
                "canonical_key": canonical_key(name),
                "partner_type": "channelizing_agency",
                "source_url": url,
                "status": "active",
                "latitude": None,
                "longitude": None,
            }
        )
    seen = set()
    unique = []
    for p in partners:
        if p["canonical_key"] in seen:
            continue
        seen.add(p["canonical_key"])
        unique.append(p)
    return unique[:100]


def extract_partner_categories(text: str, url: str = "") -> list[dict[str, Any]]:
    """Extract channel partner category rows when individual agency lists are PDF-only."""
    # Allow FAQ/partner pages; block careers
    u = (url or "").lower()
    if any(b in u for b in ("career", "recruit", "interview", "vacancy", "hr/")):
        return []

    categories = [
        ("State Channelizing Agencies (SCAs)", "state_channelizing_agency"),
        ("Public Sector Banks (PSBs)", "public_sector_bank"),
        ("Regional Rural Banks (RRBs)", "regional_rural_bank"),
        ("Non-Banking Financial Company (NBFC-MFI)", "nbfc_mfi"),
        ("Co-operative Banks", "cooperative_bank"),
        ("Small Finance Banks (SFBs)", "small_finance_bank"),
        ("Cooperative Societies", "cooperative_society"),
        ("SIDBI (Development Bank channel)", "development_bank"),
    ]
    found = []
    # Require an explicit partner-context cue in page text/url
    partner_cue = re.search(
        r"\b(channel\s*partners?|channelising|channelizing|state\s+channelizing|SCAs?)\b",
        f"{url}\n{text}",
        re.I,
    )
    if not partner_cue and "faq" not in u:
        return []

    for label, ptype in categories:
        needle = label.split("(")[0].strip()
        if re.search(re.escape(needle), text, re.I) or re.search(re.escape(label), text, re.I):
            found.append(
                {
                    "name": label,
                    "canonical_key": canonical_key(f"nsfdc-partner-category-{label}"),
                    "partner_type": ptype,
                    "organization": "NSFDC Channel Partner Category",
                    "source_url": url,
                    "status": "active",
                    "latitude": None,
                    "longitude": None,
                    "address": None,
                }
            )
    return found
